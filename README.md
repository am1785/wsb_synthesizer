# wsb_synthesizer
An informative command line tool that helps with synthesizing the most popular stock over at r/wallstreetbets subreddit for the past 24 hours.

## Prerequisites
Have a reddit account, create a reddit applicaiton, and use your credentials to set up Oauth2.
Guides for setting up Oauth2 for Reddit: https://github.com/reddit-archive/reddit/wiki/OAuth2
https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example

Aterwards, pass in your credentials into the secrets.py file and launch synthesizer.py.

You should see status code: 200 if everything is correctly set up.

## Required Python Packages
re, sqlite3, pandas, numpy, seaborn, matplotlib

## Functions

### info
Display the most recent market information on the stock of interest.

### yolo
List non-serious reddit posts on r/wsb in regards to the most popular stock

### dd
List r/wsb posts flaired by Due Diligence.

### tech
List r/wsb posts flaired by Technical Analysis
