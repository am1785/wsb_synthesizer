import secrets as secrets
import requests
import requests.auth
import json
from requests_oauthlib import OAuth2
import pandas as pd
import numpy as np
import seaborn as sns
import re
import sqlite3


def get_reddit_token():
    client_auth = requests.auth.HTTPBasicAuth(secrets.reddit_app_id, secrets.reddit_secret)
    headers = secrets.reddit_header
    post_data = secrets.post_data

    response = requests.post("https://www.reddit.com/api/v1/access_token", auth=client_auth, data=post_data, headers=headers)
    access = response.json()

    token = 'bearer ' + access['access_token']
    headers = {'Authorization': token, "User-Agent": "Windows:best_posts:v1.0 (by /u/freedom8888871)"}


    res = requests.get("https://oauth.reddit.com/r/wallstreetbets/new", headers=headers)
    print("Test Oauth2 Status Code: ", res.status_code)
    return token

def get_cached_posts():
    ''' Attempt to retrieve relevant r/wsb posts from sqlite database

    Parameters
    ----------
    None

    Returns
    -------
    list (if table exists in db)
        a list of sets containing data on the relevant posts
    Nonetype (if table not found in db)
    '''
    connection = sqlite3.connect("wsb_synthesizer.sqlite")
    with connection:
        cursor = connection.cursor()
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='wsb_posts'")
        if cursor.fetchone()[0] ==1:
            print("\nLoading posts from cache ...\n")
            select_query = "SELECT * FROM wsb_posts"
            result = cursor.execute(select_query).fetchall()
            return result

def get_posts(header, flair=None, category='top'):
    ''' Retrieve daily reddit posts and comments

    Parameters
    ----------
    category: string that indicates type of reddit post (new, hot, top, rising)
    flair (optional): string that indicates flair post within r/wsb
    header: dict that contains access token and User Agent information

    Returns
    -------
    dictionary
        a list of up to 100 r/wsb posts and its data
    '''
    url = "https://oauth.reddit.com/r/wallstreetbets/" + category
    params = {'t': 'day', 'limit': 100}
    res = requests.get(url, headers=headers, params=params)
    print(res.status_code)
    print('Fetching top posts today from oauth.reddit.com ...')
    data = res.json()
    return data

def get_popular_stock(post_listing):
    ''' Calculate the most talked about stock symbol

    Parameters
    ----------
    post_listing: list of dictionaries that contain r/wsb posts

    Returns
    -------
    string
        symbol of most popular stock on r/wsb over the past 24hrs
    '''
    from string import punctuation
    symbol_dict = {}
    punc = set(punctuation)
    STOP_WORDS = ['YOLO', 'I', 'AND', 'HOLD']
    STOP_WORDS.extend(punc)
    re_symbol = re.compile('^(?!.*[a-z\d]).+$')
    for post in post_listing['data']['children']:
        for word in (post['data']['title']).split(' '):
            matched_word = re_symbol.match(word)
            if matched_word is not None and matched_word.group(0) not in STOP_WORDS:
                matched_word = matched_word.group(0)
                if matched_word.startswith('$'):
                    matched_word = matched_word.replace('$', '')
                if matched_word.endswith('.'):
                    matched_word = matched_word.replace('.', '')
                if matched_word.endswith(','):
                    matched_word = matched_word.replace(',', '')
                if matched_word.endswith('!'):
                    matched_word = matched_word.replace('!', '')
                if matched_word in symbol_dict:
                    symbol_dict[matched_word] += 1
                else:
                    symbol_dict[matched_word] = 1
    print(symbol_dict)
    print(f"\nMost popular r/wsb stock of the day: \n♔ ♔  {max(symbol_dict, key=symbol_dict.get)} ♔ ♔\n")
    return (max(symbol_dict, key=symbol_dict.get))

def get_popular_posts(stock, post_listing):
    ''' Retriving posts relevant to the most popular stock and storing it into database

    Parameters
    ----------
    stock: string of stock symbol
    post_listing: list of dictionaries that contain r/wsb posts

    Returns
    -------
    list
        list of dictionaries that contain all the relevant information regarding the
    '''
    results = []
    for post in post_listing['data']['children']:
        if stock in post['data']['title'] or stock in post['data']['selftext']:
            result = {'url': "https://reddit.com" + post['data']['permalink'], 'stock': stock,
            'upvote': post['data'].get('ups'), 'title': post['data']['title'],
            'post_text': post['data'].get('selftext'), 'flair': post['data'].get('link_flair_text')}

            results.append(result)
            # Writing to database
            create_query =\
                '''
                CREATE TABLE IF NOT EXISTS wsb_posts(url TEXT PRIMARY KEY, stock TEXT, upvote INT,
                title TEXT, post_text TEXT, flair TEXT);
                '''
            insert_query =\
                '''
                INSERT OR IGNORE INTO wsb_posts VALUES(:url, :stock, :upvote, :title, :post_text, :flair);
                '''

            try:
                connection = sqlite3.connect("wsb_synthesizer.sqlite")
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(create_query)
                    cursor.execute(insert_query, result)
                    print('Writing most relevant r/wsb post to database...\n')
            except sqlite3.Error as e:
                print(f"Error {e.args[0]}")
    return results

if __name__ == "__main__":

    base_url = 'https://oauth.reddit.com'
    token = get_reddit_token()
    headers = {'Authorization': token, "User-Agent": "Windows:best_posts:v1.0 (by /u/freedom8888871)"}

    try:
        connection = sqlite3.connect("wsb_synthesizer.sqlite")
        with connection:
            cursor = connection.cursor()
            drop_query = "DROP TABLE IF EXISTS wsb_posts;"
            cursor.execute(drop_query)
    except sqlite3.Error as e:
        print(f"Error {e.args[0]}")

    res = ""
    while res.lower() != 'exit':
        print('Welcome to r/wsb sythensizer!')
        res = input('Press Enter to see today\'s most talked about stock on r/wallstreetbets!')
        wsb_posts = get_cached_posts()
        if wsb_posts is None:
            wsb_posts = get_posts(headers)
            POPULAR_STOCK = get_popular_stock(wsb_posts)
            relevant_posts = get_popular_posts(POPULAR_STOCK, wsb_posts)
            count = 1
            for post in relevant_posts:
                print(f"[{count}] {post['title'][:50]}")
                count +=1
        else:
            count = 1
            for post in wsb_posts:
                print(f"[{count}] {post[3]}")
                count += 1
        print("\n-------------------------------------------------------------------------")
        print('\ntype `info` for more stock info, or type flairs: `YOLO`, `DD`, `TECH` for other r/wsb posts this week.')
        print('`exit` to exit')
        res = input('YOLO = nonserious posts, DD = due diligence, TECH = technical analysis')
