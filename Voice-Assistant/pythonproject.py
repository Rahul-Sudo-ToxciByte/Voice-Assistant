import datetime
import os
import webbrowser

import pyttsx3
import speech_recognition as sr
import wikipedia

engine = pyttsx3.init('sapi5')

voices= engine.getProperty('voices') #getting details of current voice

engine.setProperty('voice', voices[1].id)

def speak(audio):
    engine.say(audio) 
    engine.runAndWait()

def wishme():
    hour=int(datetime.datetime.now().hour)
    if hour>=0 and hour<12:
        speak("Good Morning  sir!")

    elif hour>=12 and hour<18:
        speak("Good Afternoon sir!")   

    else:
        speak("Good Evening SIR! ")  
        speak(" PLEASE    TELL    ME    HOW    MAY    I    HELP      YOU")
def takeCommand():
    #It takes microphone input from the user and returns string output

    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:
        print("Recognizing...")    
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}\n")

    except Exception as e:
        # print(e)    
        print("Say that again please...")  
        return "None"
    return query     
def takeCommand():
    #It takes microphone input from the user and returns string output

    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:
        print("Recognizing...")    
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}\n")

    except Exception as e:
        # print(e)    
        print("Say that again please...")  
        return "None"
    return query

if __name__=="__main__":
    wishme()
    while True:
        query= takeCommand().lower()
        if 'wikipedia' in query:
            speak('Searching Wikipedia...')
            query = query.replace("wikipedia", "")
            results = wikipedia.summary(query, sentences=2)
            speak("According to Wikipedia")
            print(results)
            speak(results)

        elif 'open youtube' in query:
            webbrowser.open("youtube.com")
        elif 'exit' in query:
            speak("THANK YOU.")
            exit()

        elif 'open google' in query:
            webbrowser.open("google.com")
        elif 'open notepad' in query:
            notepad="C:\\Windows\\notepad.exe"
            os.startfile(notepad)
        elif 'introduce yourself' in query:    
            speak("HELLO        EVERYONE       ,     I  AM  ENCO ENCO ,            A   PYTHON  BASED    VOICE        ASSISTANT         DEVELOPED          BY         RAHUL  &  TEAM ")
