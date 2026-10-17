#!/usr/bin/env python3
"""Generate train and eval datasets for Airo Actions Function Calling SLM."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from slm_train_eval_publish.airo_actions import (
    GENERAL_REFUSAL_RESPONSE,
    GOOGLE_REFUSAL_RESPONSE,
    ROUTE_TARGETS,
    AiroActionExample,
    format_tool_call,
)

EVAL_DATE_SYSTEM_NOTE = "Today is Friday, 2026-10-16"


def create_eval_dataset() -> list[AiroActionExample]:
    examples: list[AiroActionExample] = []

    # 1. get_current_date_time (45 eval prompts)
    get_dt_prompts = [
        "What's the current date and time?",
        "What time is it right now?",
        "What is today's date?",
        "Current timezone and time please.",
        "Tell me what day of the week it is.",
        "What day is today?",
        "Check the exact local time.",
        "Could you tell me the current time?",
        "What's the date today?",
        "What is the current time and day?",
        "Tell me today's date and the weekday.",
        "I need the current local date and time.",
        "Can you check what time it is?",
        "What is the present time and timezone?",
        "Current time please.",
        "Show current time and date.",
        "What weekday is it today?",
        "What's today's full date?",
        "Check local time right now.",
        "Give me the current timestamp.",
        "What time and date is it at this moment?",
        "Could you check the current date?",
        "Tell me the time right now.",
        "Please provide the current date and time.",
        # Hinglish
        "Abhi kya time ho raha hai?",
        "Aaj ki date kya hai?",
        "Aaj kaun sa din hai?",
        "Time kya hua hai abhi?",
        "Samay kya hua hai?",
        "Aaj konsi taarikh hai?",
        "Kitne baje hain abhi?",
        "Current date aur time batao.",
        "Mera local time check karo.",
        "Aaj ka din kaun sa hai batao.",
        "Abhi kitne baj rahe hain?",
        "Mujhe aaj ki taarikh aur samay chahiye.",
        "Aaj ka date bataiye please.",
        "Current timezone aur time kya hai?",
        "Abhi exact time kya chal raha hai?",
        "Aaj kaun sa vaar hai?",
        "Check karo abhi kya time hai.",
        "Batao abhi kitna baje hain.",
        "Aaj ki date aur day confirm karo.",
        "Kya time hua hai abhi ke waqt?",
        "Abhi ka samay aur taarikh batao.",
    ]
    for p in get_dt_prompts:
        examples.append(
            AiroActionExample(
                instruction=p,
                input="",
                output=format_tool_call("get_current_date_time", {}),
                tool="get_current_date_time",
                args={},
            )
        )

    # 2. read_calendar_events (45 eval prompts)
    calendar_eval_items = [
        ("What's on my calendar tomorrow?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("What events do I have scheduled for today?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-16"}),
        ("Check my calendar for tomorrow morning.", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("Do I have any meetings tomorrow?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("What is on my schedule for today?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-16"}),
        ("Show my calendar events for 2026-10-20.", "", {"date": "2026-10-20"}),
        ("What do I have scheduled on 2026-10-22?", "", {"date": "2026-10-22"}),
        ("Read calendar events for 2026-11-05.", "", {"date": "2026-11-05"}),
        ("Check my agenda for 2026-10-28.", "", {"date": "2026-10-28"}),
        ("Any appointments on 2026-12-01?", "", {"date": "2026-12-01"}),
        ("Show meetings on 2026-11-15.", "", {"date": "2026-11-15"}),
        ("What is booked on 2026-10-25?", "", {"date": "2026-10-25"}),
        ("Check my schedule on 2026-10-31.", "", {"date": "2026-10-31"}),
        ("Read my schedule for 2026-11-20.", "", {"date": "2026-11-20"}),
        ("What events are listed for 2026-10-19?", "", {"date": "2026-10-19"}),
        ("Show appointments between 2026-10-20 and 2026-10-24.", "", {"date": "2026-10-20", "end_date": "2026-10-24"}),
        ("Check my calendar from 2026-11-01 to 2026-11-07.", "", {"date": "2026-11-01", "end_date": "2026-11-07"}),
        ("What meetings do I have between 2026-10-26 and 2026-10-30?", "", {"date": "2026-10-26", "end_date": "2026-10-30"}),
        ("List all events from 2026-11-10 to 2026-11-14.", "", {"date": "2026-11-10", "end_date": "2026-11-14"}),
        ("Read calendar entries between 2026-12-01 and 2026-12-05.", "", {"date": "2026-12-01", "end_date": "2026-12-05"}),
        ("Show schedule from 2026-10-22 to 2026-10-25.", "", {"date": "2026-10-22", "end_date": "2026-10-25"}),
        ("Check appointments between 2026-11-15 and 2026-11-18.", "", {"date": "2026-11-15", "end_date": "2026-11-18"}),
        ("Find all events on 2026-10-24.", "", {"date": "2026-10-24"}),
        ("Fetch meetings for 2026-11-02.", "", {"date": "2026-11-02"}),
        # Hinglish
        ("Kal ke meetings dikhao.", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("Aaj mera kya schedule hai calendar mein?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-16"}),
        ("Kal calendar mein kya kya hai?", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("Mera kal ka program dikhao.", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-17"}),
        ("Aaj ke saare events check karo.", EVAL_DATE_SYSTEM_NOTE, {"date": "2026-10-16"}),
        ("2026-10-20 ke events check karo.", "", {"date": "2026-10-20"}),
        ("Mera calendar check karo 2026-10-25 ke liye.", "", {"date": "2026-10-25"}),
        ("2026-11-05 ko kya plans hain?", "", {"date": "2026-11-05"}),
        ("2026-10-30 ki meeting details dikhao.", "", {"date": "2026-10-30"}),
        ("2026-11-12 ke calendar events dikhao.", "", {"date": "2026-11-12"}),
        ("Kya 2026-10-27 ko koi appointment hai?", "", {"date": "2026-10-27"}),
        ("2026-11-01 ka calendar padho.", "", {"date": "2026-11-01"}),
        ("2026-10-23 ke schedule mein kya hai?", "", {"date": "2026-10-23"}),
        ("2026-10-20 se 2026-10-25 tak ke meetings dikhao.", "", {"date": "2026-10-20", "end_date": "2026-10-25"}),
        ("Calendar check karo 2026-11-01 se 2026-11-06 tak.", "", {"date": "2026-11-01", "end_date": "2026-11-06"}),
        ("Agla hafta 2026-10-19 se 2026-10-24 tak kya events hain?", "", {"date": "2026-10-19", "end_date": "2026-10-24"}),
        ("Mera schedule dikhao 2026-11-10 se 2026-11-15 ke beech.", "", {"date": "2026-11-10", "end_date": "2026-11-15"}),
        ("2026-12-01 se 2026-12-05 tak ka calendar dikhana.", "", {"date": "2026-12-01", "end_date": "2026-12-05"}),
        ("2026-10-29 ke saare meetings list karo.", "", {"date": "2026-10-29"}),
        ("2026-11-08 ko kya schedule fix hai?", "", {"date": "2026-11-08"}),
        ("Calendar events dikhao 2026-10-21 ke.", "", {"date": "2026-10-21"}),
    ]
    for instr, inp, args in calendar_eval_items:
        examples.append(
            AiroActionExample(
                instruction=instr,
                input=inp,
                output=format_tool_call("read_calendar_events", args),
                tool="read_calendar_events",
                args=args,
            )
        )

    # 3. calendar_permission_status (45 eval prompts)
    perm_eval_prompts = [
        "Do you have access to my calendar?",
        "Can you read my calendar events?",
        "Check calendar permission status.",
        "Is calendar access granted?",
        "Do I have calendar reading enabled?",
        "Check if calendar permission is active.",
        "Are you allowed to read my calendar?",
        "Can you view my calendar appointments?",
        "Verify my calendar permissions.",
        "Check whether calendar access has been permitted.",
        "Do you possess calendar read permissions?",
        "Is calendar read privilege available?",
        "Check if you have calendar access rights.",
        "Can this assistant access device calendar?",
        "Tell me my calendar permission state.",
        "Is calendar access enabled right now?",
        "Do you have authorization to read calendar?",
        "Check calendar access authorization.",
        "Can you see my schedule permissions?",
        "Is reading calendar permitted on this device?",
        "Check if calendar permission was granted by user.",
        "Has calendar permission been provided?",
        "Check my calendar access state.",
        # Hinglish
        "Kya tumhe mere calendar ka access hai?",
        "Calendar permission status check karo.",
        "Kya calendar read karne ki permission mili hui hai?",
        "Calendar access allow hai ya nahi?",
        "Permission status kya hai calendar ka?",
        "Check karo kya app calendar padh sakti hai?",
        "Calendar permission enable hai kya?",
        "Tumhare paas calendar dekhne ki permission hai?",
        "Batao calendar access mila hai ya nahi.",
        "Calendar read permission check karke batao.",
        "Kya calendar dekhne ki permission on hai?",
        "Calendar permission grant hui hai ya deny?",
        "Mere calendar ka permission status kya hai?",
        "Check karo calendar access hai ya nahi.",
        "Calendar reading allowed hai kya?",
        "Kya main tumhe calendar access de chuka hoon?",
        "Device calendar permission verify karo.",
        "Calendar permission ka halat kya hai?",
        "Calendar allow kiya hua hai kya maine?",
        "Kya assistant calendar events access kar sakta hai?",
        "Calendar permission status bata do.",
        "Check kijiye calendar access hai ya nahi.",
    ]
    for p in perm_eval_prompts:
        examples.append(
            AiroActionExample(
                instruction=p,
                input="",
                output=format_tool_call("calendar_permission_status", {}),
                tool="calendar_permission_status",
                args={},
            )
        )

    # 4. query_lifetrack_status (45 eval prompts)
    query_eval_items = [
        "How many steps have I walked today?",
        "Did I reach my daily water intake goal?",
        "What's my reading goal progress this week?",
        "How many hours did I sleep last night?",
        "Did I hit my 10,000 steps target today?",
        "What is my current savings goal status?",
        "How much money have I saved this month on LifeTrack?",
        "Did I complete my gym workout goal today?",
        "Check my meditation streak status.",
        "How many calories have I burned so far?",
        "What is my progress on the marathon goal?",
        "Did I finish my 30 minutes reading target?",
        "What is my water drinking progress today?",
        "Check my status on the coding challenge habit.",
        "How many glasses of water did I drink today?",
        "What's my sleep score and total hours?",
        "Am I on track for my monthly investment goal?",
        "How close am I to reaching my 5km run goal?",
        "Check progress on my daily pushups challenge.",
        "What is my study goal status for today?",
        "Did I achieve my intermittent fasting goal?",
        "How many active minutes did I log today?",
        "Show my progress on the yoga habit.",
        # Hinglish
        "Aaj kitne steps chale maine?",
        "Paani peene ka goal complete hua kya aaj?",
        "Mera gym workout goal kaisa chal raha hai?",
        "Kal raat kitne ghante soye the?",
        "Aaj 10,000 steps poore hue ya nahi?",
        "Mera savings target kaisa chal raha hai?",
        "Kitne glass paani piya maine aaj?",
        "Reading goal ka progress kitna hua iss hafte?",
        "Aaj ka meditation status kya hai?",
        "Kya mera walking goal poora ho gaya?",
        "LifeTrack par running goal kitna bacha hai?",
        "Calorie burn karne ka status dikhao.",
        "Aaj ka study target hit hua kya?",
        "Bachat ka target kitna percent poora hua?",
        "Water intake goal mein kitna paani baki hai?",
        "Sleep hours kitne record hue kal raat ke?",
        "Pushups challenge ka status check karo.",
        "Coding practice streak kitni chal rahi hai?",
        "Aaj ka exercise goal complete hua ya baki hai?",
        "Weight loss goal ka current status batao.",
        "Mera weekly fitness goal kaisa chal raha hai?",
        "Kitna distance run kiya maine iss hafte?",
    ]
    for q in query_eval_items:
        examples.append(
            AiroActionExample(
                instruction=q,
                input="",
                output=format_tool_call("query_lifetrack_status", {"query": q}),
                tool="query_lifetrack_status",
                args={"query": q},
            )
        )

    # 5. open_route (45 eval prompts across 11 targets)
    route_eval_items = [
        ("Show my budget.", {"target": "budget"}),
        ("Open my budget planner screen.", {"target": "budget"}),
        ("View my monthly budget.", {"target": "budget"}),
        ("Check budget dashboard.", {"target": "budget"}),
        ("Show my expenses.", {"target": "expenses"}),
        ("Track my daily expenses.", {"target": "expenses"}),
        ("Open the expense tracker.", {"target": "expenses"}),
        ("View all expenses.", {"target": "expenses"}),
        ("Split a bill.", {"target": "split"}),
        ("Split the dinner check with friends.", {"target": "split"}),
        ("Open the bill split calculator.", {"target": "split"}),
        ("Divide expenses with roommates.", {"target": "split"}),
        ("Open money manager.", {"target": "money"}),
        ("Show my money overview.", {"target": "money"}),
        ("Take me to financial money screen.", {"target": "money"}),
        ("Go to assistant settings.", {"target": "assistant"}),
        ("Open assistant panel.", {"target": "assistant"}),
        ("Navigate to assistant route.", {"target": "assistant"}),
        ("Open models screen.", {"target": "models"}),
        ("Show downloaded AI models.", {"target": "models"}),
        ("Open model library screen.", {"target": "models"}),
        ("open music", {"target": "music"}),
        ("play music", {"target": "music"}),
        ("Open music player.", {"target": "music"}),
        ("Start beats audio music.", {"target": "music"}),
        ("Switch to TV mode.", {"target": "tv"}),
        ("Open live TV.", {"target": "tv"}),
        ("Watch TV channels.", {"target": "tv"}),
        ("Let's play games.", {"target": "games"}),
        ("Open the games section.", {"target": "games"}),
        ("Launch mini games.", {"target": "games"}),
        ("play chess", {"target": "chess"}),
        ("Start a chess game.", {"target": "chess"}),
        ("Open chess board.", {"target": "chess"}),
        ("Start a new quest.", {"target": "quest"}),
        ("Open quest dashboard.", {"target": "quest"}),
        ("View my active quests.", {"target": "quest"}),
        # Hinglish
        ("Mera budget dikhao.", {"target": "budget"}),
        ("Kharcha screen kholo.", {"target": "expenses"}),
        ("Doston ke saath bill baanto.", {"target": "split"}),
        ("Paisa dashboard open karo.", {"target": "money"}),
        ("Assistant ki settings mein le jao.", {"target": "assistant"}),
        ("Models wali library screen kholo.", {"target": "models"}),
        ("Gaana sunna hai music chalao.", {"target": "music"}),
        ("TV screen open karo.", {"target": "tv"}),
        ("Games khelna hai kholo.", {"target": "games"}),
        ("Chess khelna hai mujhe.", {"target": "chess"}),
        ("Quest list dikhao.", {"target": "quest"}),
    ]
    for instr, args in route_eval_items:
        examples.append(
            AiroActionExample(
                instruction=instr,
                input="",
                output=format_tool_call("open_route", args),
                tool="open_route",
                args=args,
            )
        )

    # 6. schedule_notification (45 eval prompts)
    notif_eval_items = [
        ("Remind me at 7:30 to take the medicine", "", {"title": "Medicine", "message": "Take the medicine", "hour": 7, "minute": 30, "repeat_daily": True}),
        ("Remind me at 14:00 to call mom.", "", {"title": "Call Mom", "message": "Call mom", "hour": 14, "minute": 0}),
        ("Set a reminder at 9:15 to submit project report.", "", {"title": "Submit Report", "message": "Submit project report", "hour": 9, "minute": 15}),
        ("Remind me every day at 8:00 to drink water.", "", {"title": "Drink Water", "message": "Drink water", "hour": 8, "minute": 0, "repeat_daily": True}),
        ("Daily reminder at 21:00 to read a book.", "", {"title": "Read Book", "message": "Read a book", "hour": 21, "minute": 0, "repeat_daily": True}),
        ("Remind me every morning at 6:30 for morning walk.", "", {"title": "Morning Walk", "message": "Morning walk", "hour": 6, "minute": 30, "repeat_daily": True}),
        ("Set notification at 17:45 for evening meeting.", "", {"title": "Meeting", "message": "Evening meeting", "hour": 17, "minute": 45}),
        ("Remind me on 2026-10-25 at 16:30 for dentist appointment.", "", {"title": "Dentist Appointment", "message": "Dentist appointment", "hour": 16, "minute": 30, "date": "2026-10-25"}),
        ("Set a reminder on 2026-11-04 at 11:00 to pay electric bill.", "", {"title": "Pay Bill", "message": "Pay electric bill", "hour": 11, "minute": 0, "date": "2026-11-04"}),
        ("Schedule reminder on 2026-10-30 at 10:00 for team sprint demo.", "", {"title": "Sprint Demo", "message": "Team sprint demo", "hour": 10, "minute": 0, "date": "2026-10-30"}),
        ("Remind me at 12:30 to take lunch.", "", {"title": "Lunch", "message": "Take lunch", "hour": 12, "minute": 30}),
        ("Set an alert for 15:00 to review pull request.", "", {"title": "Review PR", "message": "Review pull request", "hour": 15, "minute": 0}),
        ("Notify me at 19:00 to pick up groceries.", "", {"title": "Groceries", "message": "Pick up groceries", "hour": 19, "minute": 0}),
        ("Remind me at 22:00 every night to turn off lights.", "", {"title": "Turn Off Lights", "message": "Turn off lights", "hour": 22, "minute": 0, "repeat_daily": True}),
        ("Daily alert at 7:00 to take vitamins.", "", {"title": "Vitamins", "message": "Take vitamins", "hour": 7, "minute": 0, "repeat_daily": True}),
        ("Remind me tomorrow at 8:30 to water plants.", EVAL_DATE_SYSTEM_NOTE, {"title": "Water Plants", "message": "Water plants", "hour": 8, "minute": 30, "date": "2026-10-17"}),
        ("Wake me up tomorrow at 6:00.", EVAL_DATE_SYSTEM_NOTE, {"title": "Wake Up", "message": "Wake up", "hour": 6, "minute": 0, "date": "2026-10-17"}),
        ("Remind me at 13:15 to reply to client email.", "", {"title": "Client Email", "message": "Reply to client email", "hour": 13, "minute": 15}),
        ("Set reminder at 20:00 for yoga class.", "", {"title": "Yoga Class", "message": "Yoga class", "hour": 20, "minute": 0}),
        ("Remind me on 2026-11-15 at 18:00 for flight checkin.", "", {"title": "Flight Checkin", "message": "Flight checkin", "hour": 18, "minute": 0, "date": "2026-11-15"}),
        ("Alert me at 16:15 to drink green tea.", "", {"title": "Green Tea", "message": "Drink green tea", "hour": 16, "minute": 15}),
        ("Remind me every day at 12:00 to take a break.", "", {"title": "Break", "message": "Take a break", "hour": 12, "minute": 0, "repeat_daily": True}),
        ("Schedule notification at 23:00 to sleep.", "", {"title": "Sleep", "message": "Time to sleep", "hour": 23, "minute": 0}),
        # Hinglish
        ("Roz subah 7 baje dawa lene ka reminder lagao.", "", {"title": "Medicine", "message": "Dawa lena", "hour": 7, "minute": 0, "repeat_daily": True}),
        ("Subah 6 baje jagao gym ke liye.", "", {"title": "Gym", "message": "Gym ke liye uthna", "hour": 6, "minute": 0}),
        ("Raat ko 10 baje reminder do kitab padhne ka.", "", {"title": "Reading", "message": "Kitab padhna", "hour": 22, "minute": 0}),
        ("Dopahar 2 baje meeting ka notification set karo.", "", {"title": "Meeting", "message": "Meeting time", "hour": 14, "minute": 0}),
        ("Roz raat 11 baje sone ka reminder lagao.", "", {"title": "Sleep", "message": "Sone ka waqt", "hour": 23, "minute": 0, "repeat_daily": True}),
        ("Shaam 5:30 par chai peene ka reminder do.", "", {"title": "Tea Break", "message": "Chai peena", "hour": 17, "minute": 30}),
        ("Roz subah 8:00 baje exercise ka reminder set karo.", "", {"title": "Exercise", "message": "Exercise time", "hour": 8, "minute": 0, "repeat_daily": True}),
        ("Kal subah 9 baje bill pay karne ka reminder lagana.", EVAL_DATE_SYSTEM_NOTE, {"title": "Pay Bill", "message": "Bill payment", "hour": 9, "minute": 0, "date": "2026-10-17"}),
        ("2026-10-25 ko dopahar 3 baje car service ka reminder lagao.", "", {"title": "Car Service", "message": "Car servicing", "hour": 15, "minute": 0, "date": "2026-10-25"}),
        ("Har roz shaam 6 baje walk par jaane ka notification do.", "", {"title": "Walk", "message": "Evening walk", "hour": 18, "minute": 0, "repeat_daily": True}),
        ("Subah 7:45 baje office nikalne ka alert lagao.", "", {"title": "Office", "message": "Office nikalna", "hour": 7, "minute": 45}),
        ("Roz dopahar 1 baje lunch karne ka reminder set karo.", "", {"title": "Lunch", "message": "Lunch time", "hour": 13, "minute": 0, "repeat_daily": True}),
        ("Shaam 7 baje sabzi lane ka reminder set karo.", "", {"title": "Groceries", "message": "Sabzi lana", "hour": 19, "minute": 0}),
        ("Raat 9:30 par walk karne ka reminder do.", "", {"title": "Night Walk", "message": "Walk karna", "hour": 21, "minute": 30}),
        ("2026-11-01 ko subah 10 baje rent dene ka reminder lagao.", "", {"title": "Rent", "message": "Pay rent", "hour": 10, "minute": 0, "date": "2026-11-01"}),
        ("Kal shaam 4 baje doctor visit ka reminder do.", EVAL_DATE_SYSTEM_NOTE, {"title": "Doctor", "message": "Doctor appointment", "hour": 16, "minute": 0, "date": "2026-10-17"}),
        ("Roz subah 5:30 baje dhyan karne ka reminder set karo.", "", {"title": "Meditation", "message": "Meditation time", "hour": 5, "minute": 30, "repeat_daily": True}),
        ("Dopahar 3:15 baje code review ka reminder set karna.", "", {"title": "Code Review", "message": "Review code", "hour": 15, "minute": 15}),
        ("Shaam 8 baje paani peene ka reminder do.", "", {"title": "Drink Water", "message": "Paani peena", "hour": 20, "minute": 0}),
        ("Kal subah 7 baje airport nikalne ka reminder lagao.", EVAL_DATE_SYSTEM_NOTE, {"title": "Airport", "message": "Airport departure", "hour": 7, "minute": 0, "date": "2026-10-17"}),
        ("Har roz raat 10 baje diary likhne ka alert lagao.", "", {"title": "Diary", "message": "Diary likhna", "hour": 22, "minute": 0, "repeat_daily": True}),
        ("Subah 8:15 baje call karne ka reminder set karo.", "", {"title": "Call", "message": "Phone call", "hour": 8, "minute": 15}),
    ]
    for instr, inp, args in notif_eval_items:
        examples.append(
            AiroActionExample(
                instruction=instr,
                input=inp,
                output=format_tool_call("schedule_notification", args),
                tool="schedule_notification",
                args=args,
            )
        )

    # 7. record_lifetrack_facts (45 eval prompts)
    record_eval_items = [
        "I drank 500ml of water just now.",
        "Logged 30 minutes of cardio workout.",
        "I read 15 pages of Atomic Habits today.",
        "Completed 45 pushups this morning.",
        "Slept 8 hours last night peacefully.",
        "Walked 7,200 steps so far today.",
        "I saved 200 dollars into my emergency savings.",
        "Had a healthy salad bowl with 400 calories.",
        "Finished chapter 4 of my psychology book.",
        "Meditated for 20 minutes before breakfast.",
        "Completed 5km morning run in 28 minutes.",
        "Drank 1 liter bottle of water.",
        "Did 50 squats and 30 lunges at the gym.",
        "Recorded 7 hours and 45 minutes of deep sleep.",
        "Logged 10,500 steps for the evening walk.",
        "Deposited 50 dollars into mutual fund.",
        "Read 30 minutes of financial news.",
        "Ate oatmeal and fruits for breakfast.",
        "Did 15 minutes of stretching exercises.",
        "Walked 3 miles around the neighborhood park.",
        "Drank 2 glasses of warm water.",
        "Finished studying 2 lectures on machine learning.",
        "Did 35 pullups in total today.",
        # Hinglish
        "Maine aaj 2 litre paani piya.",
        "Aaj 10,000 steps complete ho gaye mere.",
        "Subah 45 minute gym kiya tha.",
        "Raat ko 8 ghante achhi neend aayi.",
        "Maine aaj 500 rupaye bachat account mein daale.",
        "Book ke 20 panne padh liye maine.",
        "15 minute meditation kiya subah.",
        "Aaj shaam ko 4 kilometer dauda hoon.",
        "Do glass paani piya abhi abhi.",
        "Gym mein 50 pushups lagaye aaj.",
        "7 ghante 30 minute soya kal raat.",
        "8500 steps chal liye aaj din bhar mein.",
        "Aaj lunch mein 500 calories ka khana khaya.",
        "Chapter 3 complete kar liya economics ka.",
        "1000 rupaye ki saving ki aaj.",
        "20 minute yoga kiya subah subah.",
        "Maine 1 litre paani ki botal khatam ki.",
        "Aaj 6000 steps ho chuke hain mere.",
        "Shaam ko 30 minute cardio kiya.",
        "Ek ghanta coding practice ki aaj.",
        "Subah 10 minute pranayama kiya.",
        "Dopahar mein healthy sprout salad khaya.",
    ]
    for r in record_eval_items:
        examples.append(
            AiroActionExample(
                instruction=r,
                input="",
                output=format_tool_call("record_lifetrack_facts", {"query": r}),
                tool="record_lifetrack_facts",
                args={"query": r},
            )
        )

    # 8. Refusals (60 eval prompts: Google 7 tools + Unknown requests + Ambiguous LifeTrack)
    # Google seven tools (25 items)
    google_refusals = [
        "Turn on the flashlight",
        "Turn off the flashlight please.",
        "Switch on my phone torch.",
        "Turn off torch right now.",
        "Send an email to sarah@example.com about the project.",
        "Send email to manager regarding leave.",
        "Compose and send an email to support.",
        "Create contact for Alex with phone number 9876543210.",
        "Save Dr. Sharma in my phone contacts.",
        "Add a new contact named John Doe.",
        "Show map to Central Park.",
        "Open map for directions to the airport.",
        "Show navigation map to nearby petrol pump.",
        "Open wifi settings.",
        "Turn on Wi-Fi in settings.",
        "Open my wifi configuration screen.",
        "Create calendar event: Team lunch on Friday at 1pm.",
        "Schedule calendar event Doctor Appointment on 2026-10-25 at 15:00.",
        "Add meeting with client to Google calendar.",
        # Hinglish Google tools
        "Torch jala do.",
        "Flashlight band kar do.",
        "Mummy ko email bhejo.",
        "Naya contact save karo phone mein.",
        "Airport jaane ka map dikhao.",
        "Wifi settings open karo phone ki.",
    ]
    for gr in google_refusals:
        examples.append(
            AiroActionExample(
                instruction=gr,
                input="",
                output=GOOGLE_REFUSAL_RESPONSE,
                tool=None,
                args={},
            )
        )

    # Unknown / out of scope queries (25 items)
    unknown_refusals = [
        "What is the capital of France?",
        "Write a python script to sort a list.",
        "Tell me a funny joke.",
        "What's the weather like in New Delhi?",
        "Who won the cricket world cup in 2011?",
        "Can you write a poem about autumn?",
        "Explain quantum computing in simple terms.",
        "What is the stock price of Apple today?",
        "Translate 'Good morning' into Spanish.",
        "How do I bake chocolate chip cookies?",
        "Who is the president of the United States?",
        "What is the distance from Earth to Mars?",
        "Give me a recipe for paneer butter masala.",
        "Write a short essay on climate change.",
        "Solve this math problem: 45 multiplied by 82.",
        # Hinglish unknown
        "Ek accha sa chutkula sunao.",
        "Aaj Mumbai ka mausam kaisa hai?",
        "Python mein reverse string kaise likhein?",
        "Bharat ke pradhan mantri kaun hain?",
        "Biryani banane ki recipe batao.",
        "Taj Mahal kisne banwaya tha?",
        "Kal ke cricket match ka score kya tha?",
        "Mujhe ek kahani sunao.",
        "Dollar ka rate kya chal raha hai rupaye mein?",
        "English se Hindi translation kar sakte ho?",
    ]
    for ur in unknown_refusals:
        examples.append(
            AiroActionExample(
                instruction=ur,
                input="",
                output=GENERAL_REFUSAL_RESPONSE,
                tool=None,
                args={},
            )
        )

    # Ambiguous LifeTrack queries (10 items)
    ambiguous_items = [
        ("Gym workout today", "Are you asking for your gym workout status or recording a new workout fact?"),
        ("Water intake", "Are you asking for your water intake status or recording water you drank?"),
        ("Reading goal progress or record", "Are you asking for your reading goal status or recording pages read?"),
        ("Sleep hours", "Are you asking for your sleep status or recording how many hours you slept?"),
        ("Daily steps", "Are you asking for your step count status or recording steps walked?"),
        ("Savings target status or add money", "Are you asking for your savings status or recording saved money?"),
        ("Aaj ka gym", "Kya aap gym workout ka status dekhna chahte hain ya gym fact record karna chahte hain?"),
        ("Paani ka hisaab", "Kya aap water intake status check karna chahte hain ya paani pina record karna chahte hain?"),
        ("Aaj ke steps", "Kya aap aaj ke steps ka status dekhna chahte hain ya naye steps record karna chahte hain?"),
        ("Kitab padhna", "Kya aap reading goal ka status dekhna chahte hain ya padhe hue panne record karna chahte hain?"),
    ]
    for instr, resp in ambiguous_items:
        examples.append(
            AiroActionExample(
                instruction=instr,
                input="",
                output=resp,
                tool=None,
                args={},
            )
        )

    return examples


def create_train_dataset(eval_instructions: set[str], seed: int = 42) -> list[AiroActionExample]:
    rng = random.Random(seed)
    train_examples: list[AiroActionExample] = []

    def add(ex: AiroActionExample):
        if ex.instruction in eval_instructions:
            return
        train_examples.append(ex)

    # 1. get_current_date_time templates (~350 examples)
    time_queries_en = [
        "What time is it?", "Tell me the time", "Current time please", "What is the time right now?",
        "What's the current time and date?", "What is the date today?", "Can you tell me today's date?",
        "Check local time", "Current date and time", "What day of the week is today?",
        "Tell me what time it is", "What's the date and time?", "What is today's day?",
        "Do you know the time?", "What time does it show?", "What is the exact current time?",
        "Tell me the current date", "Current time in local timezone", "What is the current local time?",
        "What day is it today?", "Show me the time right now", "Check today's date and time",
        "Can you check the current time and date?", "What's the weekday today?",
        "Give me today's date", "Tell me the local date", "What is the date and current weekday?",
    ]
    time_queries_hi = [
        "Abhi time kya hua hai?", "Samay kya hai abhi?", "Aaj ki taarikh kya hai?",
        "Aaj kaun sa din hai batao", "Abhi kitne baje hain?", "Current time batao",
        "Time bata do", "Aaj ki date batao", "Aaj kaun sa vaar hai?",
        "Abhi ka time kya hai?", "Mera local time kya ho raha hai?", "Samay bataiye",
        "Aaj ki taarikh bataiye", "Kitna time hua hai?", "Abhi ka date aur time kya hai?",
        "Check karo abhi kitne baje hain", "Aaj kaun si taarikh hai bhai?", "Time kya chal raha hai abhi?",
        "Abhi kitna baje hai bata do", "Aaj ka din aur taarikh kya hai?", "Local time check kijiye",
    ]
    prefixes = ["", "Please ", "Hey, ", "Hello, ", "Quick question: ", "Airo, ", "Can you tell me: "]
    for p in prefixes:
        for q in time_queries_en:
            add(AiroActionExample(
                instruction=f"{p}{q}".strip(),
                input="",
                output=format_tool_call("get_current_date_time", {}),
                tool="get_current_date_time",
                args={},
            ))
        for q in time_queries_hi:
            add(AiroActionExample(
                instruction=f"{p}{q}".strip(),
                input="",
                output=format_tool_call("get_current_date_time", {}),
                tool="get_current_date_time",
                args={},
            ))

    # 2. read_calendar_events templates (~400 examples)
    dates = [
        "2026-10-18", "2026-10-19", "2026-10-21", "2026-10-22", "2026-10-23",
        "2026-10-26", "2026-10-27", "2026-10-29", "2026-11-02", "2026-11-03",
        "2026-11-06", "2026-11-08", "2026-11-11", "2026-11-14", "2026-11-18",
        "2026-11-22", "2026-11-25", "2026-12-02", "2026-12-08", "2026-12-15",
    ]
    for d in dates:
        add(AiroActionExample(instruction=f"What do I have scheduled on {d}?", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"Check calendar events for {d}", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"Show my meetings on {d}", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"Any calendar appointments on {d}?", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"{d} ke meetings dikhao", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"Mera calendar check karo {d} ke liye", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))
        add(AiroActionExample(instruction=f"{d} ko kya schedule hai?", input="", output=format_tool_call("read_calendar_events", {"date": d}), tool="read_calendar_events", args={"date": d}))

    # Date ranges
    date_ranges = [
        ("2026-10-18", "2026-10-22"),
        ("2026-10-25", "2026-10-28"),
        ("2026-11-02", "2026-11-06"),
        ("2026-11-09", "2026-11-13"),
        ("2026-11-16", "2026-11-20"),
        ("2026-12-01", "2026-12-04"),
        ("2026-12-10", "2026-12-14"),
    ]
    for d1, d2 in date_ranges:
        args = {"date": d1, "end_date": d2}
        add(AiroActionExample(instruction=f"Show meetings between {d1} and {d2}", input="", output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))
        add(AiroActionExample(instruction=f"Check calendar from {d1} to {d2}", input="", output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))
        add(AiroActionExample(instruction=f"What events are scheduled from {d1} to {d2}?", input="", output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))
        add(AiroActionExample(instruction=f"{d1} se {d2} tak ke events dikhao", input="", output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))
        add(AiroActionExample(instruction=f"Calendar check karo {d1} se {d2} tak", input="", output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))

    # Relative dates with input system note
    ref_dates = [
        ("Today is Friday, 2026-10-16", "What events do I have today?", {"date": "2026-10-16"}),
        ("Today is Friday, 2026-10-16", "Check my meetings for tomorrow", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "What is on my schedule tomorrow?", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Aaj mera kya schedule hai?", {"date": "2026-10-16"}),
        ("Today is Friday, 2026-10-16", "Kal ke events dikhao", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Show events for tomorrow", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Check tomorrow's schedule", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Tomorrow's calendar events", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Kal ka calendar check karo", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Check my calendar for tomorrow morning.", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Do I have any meetings tomorrow?", {"date": "2026-10-17"}),
        ("Today is Friday, 2026-10-16", "Kal ke meetings dikhao.", {"date": "2026-10-17"}),
        ("Today is 2026-10-16", "What events do I have today?", {"date": "2026-10-16"}),
        ("Today is 2026-10-16", "Check my meetings for tomorrow", {"date": "2026-10-17"}),
        ("Today is 2026-10-16", "What is on my schedule tomorrow?", {"date": "2026-10-17"}),
        ("Today is 2026-10-16", "Aaj mera kya schedule hai?", {"date": "2026-10-16"}),
        ("Today is 2026-10-16", "Kal ke events dikhao", {"date": "2026-10-17"}),
        ("Today is 2026-10-20", "What's on my calendar tomorrow?", {"date": "2026-10-21"}),
        ("Today is Tuesday, 2026-10-20", "Check events for today", {"date": "2026-10-20"}),
        ("Today is Tuesday, 2026-10-20", "Kal kya meetings hain?", {"date": "2026-10-21"}),
        ("Today is 2026-11-01", "What's on my calendar tomorrow?", {"date": "2026-11-02"}),
        ("Today is Sunday, 2026-11-01", "Any appointments today?", {"date": "2026-11-01"}),
        ("Today is Sunday, 2026-11-01", "Meetings for tomorrow", {"date": "2026-11-02"}),
        ("Today is Monday, 2026-11-09", "Events scheduled for tomorrow", {"date": "2026-11-10"}),
        ("Today is Wednesday, 2026-11-18", "Calendar agenda for tomorrow", {"date": "2026-11-19"}),
    ]
    for note, q, args in ref_dates:
        add(AiroActionExample(instruction=q, input=note, output=format_tool_call("read_calendar_events", args), tool="read_calendar_events", args=args))

    # 3. calendar_permission_status templates (~300 examples)
    perm_queries_en = [
        "Check calendar permissions", "Do you have permission to view my calendar?",
        "Can I read calendar events with this app?", "Is calendar access granted on device?",
        "Do you have access to read my calendar?", "Check if calendar read permission is given",
        "Are calendar permissions granted?", "Tell me if you have calendar access",
        "Verify calendar read access", "Check calendar access permission",
        "Is device calendar access enabled?", "Can you check my calendar permissions?",
        "Do you have authorization to view schedule?", "Is calendar read permission enabled?",
    ]
    perm_queries_hi = [
        "Calendar permission check karo", "Kya tumhe calendar access mila hua hai?",
        "Calendar read karne ki permission hai kya?", "Device calendar permission status kya hai?",
        "Kya app calendar padh sakti hai?", "Check karo calendar permission granted hai?",
        "Calendar permission on hai ya off?", "Calendar dekhne ki permission mili hai kya?",
        "Calendar access allow kiya hai maine?", "Kya mere calendar ka access available hai?",
        "Calendar permission check karke bataiye", "Batao calendar access hai ya nahi",
    ]
    for p in prefixes:
        for q in perm_queries_en:
            add(AiroActionExample(instruction=f"{p}{q}".strip(), input="", output=format_tool_call("calendar_permission_status", {}), tool="calendar_permission_status", args={}))
        for q in perm_queries_hi:
            add(AiroActionExample(instruction=f"{p}{q}".strip(), input="", output=format_tool_call("calendar_permission_status", {}), tool="calendar_permission_status", args={}))

    # 4. query_lifetrack_status templates (~250 examples)
    lifetrack_goals = [
        ("daily steps", "steps walked today"),
        ("water intake", "daily water target"),
        ("reading habit", "reading goal progress"),
        ("sleep duration", "sleep hours last night"),
        ("workout goal", "gym workout status"),
        ("savings target", "monthly savings goal"),
        ("calorie burn", "daily calorie target"),
        ("meditation habit", "daily meditation goal"),
        ("running practice", "weekly 5k running progress"),
        ("coding challenge", "daily coding streak"),
        ("pushups habit", "pushups challenge progress"),
        ("yoga streak", "morning yoga habit"),
        ("study hours", "daily study target"),
        ("cycling distance", "weekly cycling goal"),
        ("fasting goal", "intermittent fasting window"),
    ]
    query_formats_en = [
        "What's my status on {goal}?",
        "How am I doing on my {detail}?",
        "Did I achieve my {detail} today?",
        "Show my progress for {goal}",
        "Check my {goal} status",
        "Am I on track with my {detail}?",
        "What is my current {goal}?",
        "How much {detail} have I completed?",
        "Check LifeTrack for {goal}",
        "What is the status of my {goal}?",
    ]
    query_formats_hi = [
        "{goal} ka status kya hai?",
        "Mera {detail} complete hua kya?",
        "LifeTrack par {goal} check karo",
        "Aaj ka {detail} kitna bacha hai?",
        "{goal} kaisa chal raha hai?",
        "Check karke batao mera {goal}",
        "Kya maine aaj ka {detail} poora kiya?",
    ]
    for goal_name, detail in lifetrack_goals:
        for fmt in query_formats_en:
            q = fmt.format(goal=goal_name, detail=detail)
            add(AiroActionExample(instruction=q, input="", output=format_tool_call("query_lifetrack_status", {"query": q}), tool="query_lifetrack_status", args={"query": q}))
        for fmt in query_formats_hi:
            q = fmt.format(goal=goal_name, detail=detail)
            add(AiroActionExample(instruction=q, input="", output=format_tool_call("query_lifetrack_status", {"query": q}), tool="query_lifetrack_status", args={"query": q}))

    # 5. open_route templates (~450 examples across all 11 targets)
    route_patterns = {
        "budget": [
            "show my budget", "open budget", "view my budget", "budget screen", "open budget planner",
            "take me to budget", "check my monthly budget", "mera budget dikhao", "budget screen kholo",
            "budget dashboard open karo", "budget dekhna hai", "go to my budget", "view budget",
            "open the budget view", "budget page par jao", "aaj ka budget dikhao"
        ],
        "expenses": [
            "show my expenses", "track expenses", "open expense tracker", "view my spending",
            "open expenses screen", "take me to expenses", "check my expenses today", "kharcha screen kholo",
            "kharchon ka hisaab dikhao", "expenses track karne wali screen", "mera kharcha dikhao",
            "track spending", "open my expenses log", "kharcha dashboard open karo", "view expenses"
        ],
        "split": [
            "Split a bill", "split the bill", "split expenses with friends", "open split bill screen",
            "divide bill with roommates", "split dinner check", "bill split calculator",
            "doston ke saath bill baanto", "bill split karna hai", "hisaab baantne wali screen kholo",
            "bill split option open karo", "split cost", "share expense with friends", "split view open karo"
        ],
        "money": [
            "open money", "open money manager", "show money overview", "financial money dashboard",
            "go to money screen", "take me to money section", "paisa screen open karo",
            "money dashboard kholo", "money overview dikhao", "finance screen par jao",
            "manage money", "open financial money hub", "money route par le jao"
        ],
        "assistant": [
            "go to assistant", "open assistant settings", "take me to assistant screen",
            "assistant hub", "open assistant route", "assistant panel kholo",
            "assistant screen par le chalo", "assistant settings dikhao", "switch to assistant",
            "open assistant main screen", "assistant preferences kholo"
        ],
        "models": [
            "open models", "show models screen", "open model library", "view downloaded models",
            "AI models screen", "take me to models", "models panel kholo", "models library dikhao",
            "offline models screen open karo", "model manager kholo", "view AI models list"
        ],
        "music": [
            "open music", "play music", "music player", "open beats music", "start music",
            "listen to music", "switch to music", "gaana lagao", "music chalao", "music screen open karo",
            "beats sunna hai", "gaane sunne hain", "music section par jao", "open music tab"
        ],
        "tv": [
            "open tv", "switch to tv mode", "watch tv", "open live tv", "live tv channels",
            "take me to tv", "tv screen open karo", "tv channels dikhao", "live tv chalao",
            "tv mode mein switch karo", "watch live television", "open TV guide"
        ],
        "games": [
            "open games", "let's play games", "mini games screen", "open games section",
            "start playing games", "games kholo", "khel khelna hai", "games screen open karo",
            "mini games chalao", "play a game", "take me to arcade games"
        ],
        "chess": [
            "play chess", "open chess", "start a chess match", "chess game", "take me to chess",
            "chess board open karo", "chess khelna hai", "chess match lagao", "chess start karo",
            "let's play chess", "start chess game now", "chess board dikhao"
        ],
        "quest": [
            "open quest", "start a new quest", "view my quests", "active quest dashboard",
            "take me to quest screen", "quest screen kholo", "naya quest shuru karo",
            "mera quest dikhao", "quests overview open karo", "check quests", "open active quest"
        ],
    }
    for target, phrases in route_patterns.items():
        for ph in phrases:
            add(AiroActionExample(instruction=ph, input="", output=format_tool_call("open_route", {"target": target}), tool="open_route", args={"target": target}))
            add(AiroActionExample(instruction=f"Please {ph}", input="", output=format_tool_call("open_route", {"target": target}), tool="open_route", args={"target": target}))
            add(AiroActionExample(instruction=f"Can you {ph}?", input="", output=format_tool_call("open_route", {"target": target}), tool="open_route", args={"target": target}))

    # 6. schedule_notification templates (~250 examples)
    reminder_subjects = [
        ("Medicine", "take the medicine", "dawa lene ka"),
        ("Call Mom", "call mom", "mummy ko call karne ka"),
        ("Drink Water", "drink water", "paani peene ka"),
        ("Gym", "go to gym", "gym jaane ka"),
        ("Team Meeting", "join team meeting", "meeting join karne ka"),
        ("Pay Bills", "pay utility bills", "bill bharne ka"),
        ("Doctor", "visit doctor", "doctor ke paas jaane ka"),
        ("Read Book", "read 20 pages", "kitab padhne ka"),
        ("Journal", "write evening journal", "diary likhne ka"),
        ("Groceries", "buy groceries", "sabzi lane ka"),
        ("Yoga", "practice yoga", "yoga karne ka"),
        ("Stretch", "stretch for 10 minutes", "stretching karne ka"),
        ("Standup", "join morning standup", "standup meeting ka"),
        ("Dentist", "attend dentist checkup", "dentist visit ka"),
        ("Water Plants", "water home plants", "paudhon ko paani dene ka"),
    ]
    hours = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
    minutes = [0, 15, 30, 45]
    dates_notif = ["2026-10-18", "2026-10-22", "2026-10-27", "2026-11-03", "2026-11-12", "2026-11-20"]

    for subj, msg_en, msg_hi in reminder_subjects:
        for _ in range(4):
            h = rng.choice(hours)
            m = rng.choice(minutes)
            # One-shot English
            args_once = {"title": subj, "message": msg_en.capitalize(), "hour": h, "minute": m}
            add(AiroActionExample(instruction=f"Remind me at {h}:{m:02d} to {msg_en}", input="", output=format_tool_call("schedule_notification", args_once), tool="schedule_notification", args=args_once))
            add(AiroActionExample(instruction=f"Set a reminder for {h}:{m:02d} to {msg_en}", input="", output=format_tool_call("schedule_notification", args_once), tool="schedule_notification", args=args_once))

            # Daily English
            args_daily = {"title": subj, "message": msg_en.capitalize(), "hour": h, "minute": m, "repeat_daily": True}
            add(AiroActionExample(instruction=f"Remind me every day at {h}:{m:02d} to {msg_en}", input="", output=format_tool_call("schedule_notification", args_daily), tool="schedule_notification", args=args_daily))
            add(AiroActionExample(instruction=f"Daily reminder at {h}:{m:02d} to {msg_en}", input="", output=format_tool_call("schedule_notification", args_daily), tool="schedule_notification", args=args_daily))

            # With Date
            dt = rng.choice(dates_notif)
            args_date = {"title": subj, "message": msg_en.capitalize(), "hour": h, "minute": m, "date": dt}
            add(AiroActionExample(instruction=f"Remind me on {dt} at {h}:{m:02d} to {msg_en}", input="", output=format_tool_call("schedule_notification", args_date), tool="schedule_notification", args=args_date))

            # Hinglish
            args_hi = {"title": subj, "message": msg_hi, "hour": h, "minute": m}
            add(AiroActionExample(instruction=f"{h}:{m:02d} par {msg_hi} reminder lagao", input="", output=format_tool_call("schedule_notification", args_hi), tool="schedule_notification", args=args_hi))
            add(AiroActionExample(instruction=f"Roz {h}:{m:02d} baje {msg_hi} notification set karo", input="", output=format_tool_call("schedule_notification", {**args_hi, "repeat_daily": True}), tool="schedule_notification", args={**args_hi, "repeat_daily": True}))

    # 7. record_lifetrack_facts templates (~300 examples)
    facts_en = [
        "I drank 250ml of cold water.", "Drank 500ml water after workout.", "Finished 1.5 liters of water today.",
        "Logged 45 minutes of strength training.", "Did 30 minutes of stationary bike cardio.",
        "Completed 50 pushups and 40 sit-ups.", "Ran 4 miles at an easy pace.", "Walked 8,000 steps today.",
        "Read 20 pages of clean code.", "Finished reading 1 chapter of history.", "Slept 7 hours last night.",
        "Got 8 hours of sleep.", "Saved 100 dollars into bank account.", "Saved 250 dollars this week.",
        "Meditated for 10 minutes.", "Completed 15 minutes of mindfulness practice.",
        "Ate a protein rich lunch around 550 calories.", "Had a light dinner with 350 calories.",
        "Practiced guitar for 30 minutes.", "Solved 2 leetcode problems today.",
        "Walked 5,500 steps during lunch.", "Drank 750ml of electrolyte water.",
        "Completed 3 sets of 12 pullups.", "Spent 45 minutes on deep work session.",
        "Logged 8 hours of restful sleep.", "Transferred 120 dollars to savings.",
    ]
    facts_hi = [
        "Maine 1 litre paani piya abhi.", "Do glass paani piya tha subah.", "Aaj 3 litre paani complete ho gaya.",
        "Subah 30 minute running ki.", "Gym mein 40 pushups maare.", "Shaam ko 5 kilometer walk kiya.",
        "Aaj 9000 steps chale hain.", "Raat ko 7 ghante achhi neend li.", "8 ghante soya kal raat.",
        "Maine aaj 200 rupaye bachat kiye.", "500 rupaye saving account mein daale.",
        "Kitab ke 15 page padhe aaj.", "Ek chapter padh ke khatam kiya.", "10 minute dhyan lagaya subah.",
        "Subah yoga session kiya 20 minute.", "Healthy khana khaya lunch mein.",
        "Aaj 7000 kadam chalkar poore kiye.", "Dopahar mein do kela aur seb khaya.",
        "15 minute breathing exercise kiya.", "Shaam ko 3 kilometer jogging ki.",
    ]
    for f in facts_en:
        add(AiroActionExample(instruction=f, input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))
        add(AiroActionExample(instruction=f"Record this fact: {f}", input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))
        add(AiroActionExample(instruction=f"LifeTrack fact: {f}", input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))
    for f in facts_hi:
        add(AiroActionExample(instruction=f, input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))
        add(AiroActionExample(instruction=f"LifeTrack mein note karo: {f}", input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))
        add(AiroActionExample(instruction=f"Yeh fact record karo: {f}", input="", output=format_tool_call("record_lifetrack_facts", {"query": f}), tool="record_lifetrack_facts", args={"query": f}))

    # 8. Refusals: Google 7 tools, unknown queries, ambiguous LifeTrack
    # Google tools refusals
    google_variants = [
        "Turn on torch", "Can you turn on flashlight?", "Switch on torch please", "Please turn on the torch",
        "Turn off torch", "Disable the flashlight", "Switch off the flashlight", "Turn off phone light",
        "Torch jalao", "Torch band karo", "Flashlight on karo", "Phone ki torch chalu karo",
        "Flashlight band kardo abhi", "Torch on kardo please", "Batti jalao phone ki",
        "Torch switch on karo", "Torch light band karo", "Flashlight off please",
        "Send an email to boss@company.com", "Email John the status report", "Compose email to doctor",
        "Send mail to my friend", "Mera email bhejo", "Email likh ke send karo", "Mail bhej do",
        "Send an email about project", "Email HR regarding leaves", "Mail bhejna hai manager ko",
        "Send email to coworker", "Draft email to client", "Mail send kar do team ko",
        "Create contact for Bob with phone 1234567890", "Save contact Sarah in address book",
        "Naya contact add karo", "Contact banao phone mein", "Contact save kijiye",
        "Save new contact in phone", "Add contact Rahul with phone number", "Address book mein contact dalo",
        "Add contact David 9876543210", "Phone mein naya number save karo", "Contact list mein name add karo",
        "Show map to San Francisco", "Open map and navigate to store", "Show map directions to hotel",
        "Map kholo rasta dekhne ke liye", "Google maps open karo", "Map par directions dikhao",
        "Show navigation to Mumbai airport", "Map par location search karo", "Find route on map",
        "Navigate to nearest gas station on map", "Map par rasta dikhao", "Google maps par location dikhao",
        "Open wifi settings please", "Turn on wifi", "Open settings for wifi",
        "Wifi on karke do", "Wifi settings kholo", "Wifi settings page par jao",
        "Wifi switch on karo settings mein", "Open Wi-Fi preferences", "Device wifi settings dikhao",
        "Wifi connect karne ke liye settings kholo", "Turn on Wi-Fi connection", "Configure wifi network settings",
        "Create calendar event Meeting tomorrow at 3pm", "Add event to Google Calendar for lunch on Friday",
        "Schedule calendar event for dental visit", "Calendar mein event add karo", "Naya calendar event banao",
        "Add an appointment to my Google calendar", "Calendar mein meeting book karo",
        "Schedule calendar event Team Sync on 2026-10-25 at 11:00.",
        "Schedule calendar event Client Review on 2026-11-02 at 14:00.",
        "Add doctor appointment to calendar for Monday",
        "Create calendar event Birthday Party at 7pm",
        "Google calendar mein event schedule kardo",
        "Calendar mein new meeting add karo",
        "Schedule an event in Google Calendar",
        "Create a calendar entry for project kickoff",
    ]
    for gv in google_variants:
        add(AiroActionExample(instruction=gv, input="", output=GOOGLE_REFUSAL_RESPONSE, tool=None, args={}))
        add(AiroActionExample(instruction=f"Can you {gv.lower()}?", input="", output=GOOGLE_REFUSAL_RESPONSE, tool=None, args={}))
        add(AiroActionExample(instruction=f"Please {gv.lower()}", input="", output=GOOGLE_REFUSAL_RESPONSE, tool=None, args={}))

    # Unknown general queries
    unknown_variants = [
        "What is the population of Tokyo?", "How does gravity work?", "Write a haiku about rain.",
        "Who discovered penicillin?", "What is the speed of light?", "Give me tips for good sleep.",
        "How do airplanes fly?", "What is the tallest mountain in the world?", "Summarize Shakespeare's Hamlet.",
        "What is the chemical formula for water?", "Can you write a sorting algorithm in C++?",
        "Tell me an interesting science fact.", "Who painted the Mona Lisa?", "What is machine learning?",
        "Chai kaise banate hain?", "Duniya ka sabse bada ped kaun sa hai?", "Solar system mein kitne grah hain?",
        "Cricket match kab shuru hoga?", "Roti gol kaise banayein?", "Hindi varnamala sunao.",
        "Computer kaise kaam karta hai?", "Newton ka pehla niyam kya hai?", "Pani ka formula kya hai?",
        "What is the distance to the moon?", "Who invented the telephone?", "Tell me a bedtime story.",
        "How to solve a Rubik's cube?", "What are the rules of basketball?", "Write a poem about trees.",
        "Generate a random number", "Translate 'thank you' to French", "What is photosynthesis?",
        # Math & calculation queries
        "Solve 25 multiplied by 4.", "Calculate 15 plus 85.", "What is 100 divided by 5?",
        "Solve this math problem: 12 times 15.", "Calculate 50 percent of 200.",
        "Math question: 45 minus 18.", "Calculate the square root of 81.",
        "Solve 30 multiplied by 50.", "15 times 4 kitna hota hai?", "20 plus 80 solve karo.",
        "Hisab lagao 500 minus 120.", "Math calculation: 75 divided by 3.",
        # Weather & forecast
        "What's the weather like in New York today?", "Will it rain this evening in Chicago?",
        "What is the current temperature outside?", "Weather forecast for Paris this weekend.",
        "Is it sunny or cloudy today?", "Aaj Bangalore ka mausam kaisa hai?",
        "Mausam kaisa rahega kal shaam ko?", "Kolkata mein barish hone wali hai kya?",
        "Aaj garmi zyada hai kya bahar?", "Mausam ki jankari do.",
        # Jokes & stories
        "Tell me a joke about computers.", "Make me laugh with a funny joke.",
        "Can you tell me a short bedtime story?", "Tell me a joke about space.",
        "Ek mazedaar chutkula sunao.", "Kuch hasne wali baat batao.",
        "Dosti par ek achhi kahani sunao.", "Ek chota sa joke sunao.",
        "Bachon ke liye ek kahani sunao.", "Chutkula sunao please.",
        # Sports, news & currency
        "Who won the cricket match yesterday?", "IPL match ka score kya chal raha hai?",
        "What is the gold rate today?", "Dollar to INR currency conversion rate.",
        "Stock market mein Nifty ka score kya hai?", "Rupaye ka rate dollar ke mukable kya hai?",
        "Who won the football world cup?", "Olympics 100 meter race winner kaun tha?",
        # General knowledge & translation
        "How do you say thank you in Japanese?", "Translate good morning to German.",
        "Aap kaise ho?", "Who is the Prime Minister of Australia?",
        "What is the largest ocean on Earth?", "Why is the sky blue during the day?",
        "Bharat ke rashtrapati kaun hain?", "Duniya ka sabse lamba pul kahan hai?",
    ]
    for uv in unknown_variants:
        add(AiroActionExample(instruction=uv, input="", output=GENERAL_REFUSAL_RESPONSE, tool=None, args={}))

    # Ambiguous queries (should clarify, not call tool)
    ambiguous_train = [
        ("Gym status or fact?", "Are you asking for your gym status or recording a workout fact?"),
        ("Water intake note", "Are you asking for your water intake status or recording water you drank?"),
        ("Reading challenge", "Are you asking for your reading goal status or recording pages read?"),
        ("Sleep record check", "Are you asking for your sleep status or recording how many hours you slept?"),
        ("Steps today note", "Are you asking for your step count status or recording steps walked?"),
        ("Savings info", "Are you asking for your savings status or recording saved money?"),
        ("Aaj ki exercise", "Kya aap exercise status dekhna chahte hain ya fact record karna chahte hain?"),
        ("Paani ka data", "Kya aap water status dekhna chahte hain ya paani pina record karna chahte hain?"),
        ("Cardio details", "Are you asking for your cardio status or recording cardio done?"),
        ("Meditation log", "Are you asking for your meditation status or recording meditation minutes?"),
        ("Workout entry or status?", "Are you asking for your workout status or recording a new exercise fact?"),
        ("Water drinking info", "Are you asking for your water intake status or recording water drank?"),
        ("Step count check or add", "Are you asking for your step count status or recording steps walked?"),
        ("Book reading progress or record", "Are you asking for your reading goal status or recording pages read?"),
        ("Daily walking note", "Are you asking for your step count status or recording steps walked?"),
        ("Saved funds record or status", "Are you asking for your savings status or recording saved money?"),
        ("Kadam chalne ka hisaab", "Kya aap steps status dekhna chahte hain ya naye kadam record karna chahte hain?"),
        ("Exercise ka data", "Kya aap workout status dekhna chahte hain ya exercise fact record karna chahte hain?"),
        ("Neend ka record ya status", "Kya aap sleep status check karna chahte hain ya soye hue ghante record karna chahte hain?"),
        ("Bachat ki entry ya status", "Kya aap savings status check karna chahte hain ya bachat record karna chahte hain?"),
        ("Dhyan lagana status ya fact", "Kya aap meditation status dekhna chahte hain ya meditation fact record karna chahte hain?"),
        ("Kitab padhne ka goal status ya update", "Kya aap reading goal ka status dekhna chahte hain ya padhe hue panne record karna chahte hain?"),
        ("Gym session update ya status", "Kya aap gym status dekhna chahte hain ya gym workout fact record karna chahte hain?"),
        ("Walked distance check or log", "Are you asking for your walking status or recording walked distance?"),
    ]
    for q, ans in ambiguous_train:
        add(AiroActionExample(instruction=q, input="", output=ans, tool=None, args={}))

    rng.shuffle(train_examples)
    return train_examples


def main() -> None:
    eval_examples = create_eval_dataset()
    eval_instructions = {ex.instruction for ex in eval_examples}

    train_examples = create_train_dataset(eval_instructions)
    train_instructions = {ex.instruction for ex in train_examples}

    overlap = eval_instructions.intersection(train_instructions)
    assert len(overlap) == 0, f"Leakage detected: {overlap}"

    print(f"Total Eval Examples: {len(eval_examples)}")
    print(f"Total Train Examples: {len(train_examples)}")

    # Check tool counts in eval
    from collections import Counter
    eval_tools = Counter(ex.tool if ex.tool else "refusal" for ex in eval_examples)
    print("Eval tool distribution:")
    for tool, count in sorted(eval_tools.items()):
        print(f"  {tool}: {count}")

    train_tools = Counter(ex.tool if ex.tool else "refusal" for ex in train_examples)
    print("Train tool distribution:")
    for tool, count in sorted(train_tools.items()):
        print(f"  {tool}: {count}")

    # Write files
    train_path = Path("data/processed/airo_actions_train.jsonl")
    eval_path = Path("data/processed/airo_actions_eval.jsonl")

    train_path.parent.mkdir(parents=True, exist_ok=True)

    with train_path.open("w", encoding="utf-8") as handle:
        for ex in train_examples:
            handle.write(json.dumps(ex.to_jsonl_row(), ensure_ascii=False) + "\n")

    with eval_path.open("w", encoding="utf-8") as handle:
        for ex in eval_examples:
            handle.write(json.dumps(ex.to_jsonl_row(), ensure_ascii=False) + "\n")

    print(f"Written train to: {train_path.resolve()}")
    print(f"Written eval to: {eval_path.resolve()}")


if __name__ == "__main__":
    main()
