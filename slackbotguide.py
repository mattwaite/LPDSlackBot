import os, time, requests, json, re, sqlite3
from slackclient import SlackClient
from datetime import datetime, timedelta

#----SECRET KEYS----#
BOT_ID = os.environ.get("BOT_ID")
SLACK_KEY = os.environ.get("SLACK_BOT_TOKEN")
WEATHER_KEY = os.environ.get("WEATHER_TOKEN")

#----COMMAND KEYS----#
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"
GREETING = "hey"
CURRENT_WEATHER = "weather"
FUTURE_WEATHER = "weather in"
OBJECTID = "objectid"

#----WEATHER VARIABLES----#
# These are replaced when the get_current_weather function is called.
weather_update = datetime(2000, 1, 1, 0, 0)
weather_json = ""

#----SLACK CLIENT----#
#This is needed to interact with Slack.
slack_client = SlackClient(SLACK_KEY)

#----FUNCTIONS----#
#These functions create responses based on data.

#This function responds with the current weather in Lincoln.
#If the weather data has not been updated in more than an hour, it goes and gets the current forecast from the Dark Sky API.
def get_current_weather():
    now = datetime.now()
    hour = timedelta(hours=1) #Generic hour object for later comparison
    url = "https://api.darksky.net/forecast/{0}/40.8,-96.667".format(WEATHER_KEY) #API URL
    #These global variables allow the information to be saved outside the function
    global weather_update
    global weather_json
    #If the weather data hasn't been updated in an hour, it gets new information.
    if now - weather_update > hour:
        r = requests.get(url)
        data = r.text
        weather_json = data
        weather_update = now
        print("Got new information.")
    #This parses the weather data into the relevant values.
    parsed = json.loads(weather_json)
    current_temp = int(parsed['currently']['temperature'])
    #The humidity is given as a decimal, so it's converted to a percentage.
    current_humidity = int(parsed['currently']['humidity']*100)
    current_summary = parsed['currently']['summary']
    #The response is created with the values filled in and returned.
    response = "Currently: {0} degrees, {1}% humidity. {2}.".format(current_temp, current_humidity, current_summary)
    return response

#This function responds with the weather sometime in the future in Lincoln.
#If the weather data has not been updated in more than an hour, it goes and gets the current forecast from the Dark Sky API.
def get_future_weather(command):
    now = datetime.now()
    hour = timedelta(hours=1) #Generic hour object for later comparison
    url = "https://api.darksky.net/forecast/c0ce361aef7d22995d861592fec46c43/40.8,-96.667" #API URL
    #These global variables allow the information to be saved outside the function
    global weather_update
    global weather_json
    #If the weather data hasn't been updated in an hour, it gets new information.
    if now - weather_update > hour:
        r = requests.get(url)
        data = r.text
        weather_json = data
        weather_update = now
        print("Got new information.")
    #This parses the weather data into the relevant values.
    parsed = json.loads(weather_json)
    #This searches for the first number in the command.
    message_number = re.search('\d+', command)
    #If a number is found, it is converted to an integer. If not, it responds and asks for a new command with a number.
    try:
        timechange = int(message_number.group(0))
    except:
        return "Please include how many hours you would like to move ahead using digits."
    #The data only has weather for the next 48 hours. So, if someone asks for data beyond that, it asks for a new command with a smaller number.
    if timechange > 48:
        return "Please choose a smaller number."
    #The hourly forecast is a list of lists, so it just gets the list with the index that matches the number of hours to jump ahead.
    hourly_data = parsed['hourly']['data']
    #This parses the weather data into the relevant values.
    future_data = hourly_data[timechange]
    future_temp = int(future_data['temperature'])
    #The humidity is given as a decimal, so it's converted to a percentage.
    future_humidity = int(future_data['humidity']*100)
    future_summary = future_data['summary']
    #This creates a datetime object from the forecast time so it can later be included in the response.
    future_time_object = datetime.fromtimestamp(future_data['time'])
    #The response is created with the values filled in and returned.
    response = "At {3}: {0} degrees, {1}% humidity. {2}.".format(future_temp, future_humidity, future_summary, future_time_object.strftime("%-I:%M %p on %A"))
    return response

#This function queries the database using a SQL command provided in the message
def sql_query(command):
    query = command
    #This connects to the database and prepares it for a query
    conn = sqlite3.connect("LPDdispatch.sqlite")
    c = conn.cursor()

    #This block tries to execute the query. If an error is ever thrown, it responds with a failure message.
    try:
        #This executes the query and gets the response as a list of lists.
        c.execute(query)
        all_rows = c.fetchall()

        #If the response is only one entry, it gets specific information for the response. THIS IS ALL VERY SKETCHY.
        if len(all_rows) == 1:
            row = all_rows[0]
            #If the entry has more than one field, it treats it as a full row and gets info from each column.
            if len(row) > 1:
                #This combines the date and time fields into a raw datetime field. Then, it peels off each value.
                raw_datetime = "{0}{1}".format(row[7], row[9])
                year = int(raw_datetime[:4])
                month = int(raw_datetime[4:6])
                day = int(raw_datetime[6:8])
                hour = int(raw_datetime[8:10])
                minute = int(raw_datetime[10:])
                #This creates the datetime object using the values
                date = datetime(year, month, day, hour, minute)
                #This turns it into human-readable text.
                date_text = date.strftime("%b. %-d, %Y, %-I:%M %p")
                #These get other information from the entry and title case them.
                block = row[4].title()
                category = row[3].title()
                officer = row[11].title()
                case_number = row[6]
                #If the entry has elements in the first and second fields, this assumes they are the latitude and longitude.
                if row[0] and row[1]:
                    #This creates a Google Maps link using the latitude and longitude from the entry
                    map_link = "http://maps.google.com/maps?z=12&t=h&q=loc:{1}+{0} ".format(row[0], row[1])
                    response = "{0}: {1}. {2}. Responding officer: {3}. {4}".format(date_text, category, block, officer, map_link)
                #If the first and second elements are null, it creates a response without the link.
                else:
                    response = "{0}: {1}. {2}. Responding officer: {3}.".format(date_text, category, block, officer)
                return response
            #Otherwise, if the row only has one field, it returns that field.
            else:
                response = row[0]
                return response
        #Otherwise, it returns the raw list of lists.
        else:
            response = all_rows
        return response
    except:
        return "Unable to complete your query."

#This function searches the database for an entry by its objectid.
def object_id_search(command):
    #This pre-populates the SQL query and then sends that to the sql_query function.
    query = "SELECT * FROM LPD_Dispatch_Records WHERE OBJECTID = {0}".format(command[9:])
    response = sql_query(query)
    return response

#----COMMAND HANDLING----#
#This function parses the message and figures out how to respond.
#That response can be a simple text message or it can call a function.
def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    #This is the generic response. This will be sent if someone sends something that isn't recognized.
    #You should use this to guide users.
    response = "Not sure what you mean. Try something else, like *weather*."
    #Each of these checks to see if the command starts with a certain phrase or word.
    if command.startswith(EXAMPLE_COMMAND):
        response = "Sure...write some more code then I can do that!"
    elif command.startswith(GREETING):
        response = "Hey!"
    elif command.startswith(FUTURE_WEATHER):
        response = get_future_weather(command)
    elif command.startswith(CURRENT_WEATHER):
        response = get_current_weather()
    elif command.startswith(OBJECTID):
        response = object_id_search(command)

    #Finally, once a response is created, the slack_client posts it to the same channel the original message is in.
    slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)

#----PARSING OUTPUT----#
#This function takes the output and parses it. YOU SHOULDN'T NEED TO CHANGE ANYTHING.
#If the bot is named, it returns the channel id and the message with the username removed.
#If the bot is not named, it returns None and None.
def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), output['channel']
    return None, None

#----CREATING THE TUNNEL----#
#This is called when the file is run from the terminal. YOU SHOULDN'T NEED TO CHANGE ANYTHING.
#It tries to connect to the slack client. If it fails, it prints a failure message.
if __name__ == "__main__":
    #This is how long the loop waits between checking for new messages.
    READ_WEBSOCKET_DELAY = 1
    if slack_client.rtm_connect():
        #Once the connection is successful, it starts a loop to constantly check for new messages.
        #It sends anything it finds to the parse_slack_output function.
        #If it receives a response from the parse_slack_output function, it sends those responses to the handle_command function.
        print("Bot connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID.")
