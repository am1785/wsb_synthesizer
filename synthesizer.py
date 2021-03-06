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
import datetime
import webbrowser
from matplotlib import pyplot as plt

def get_reddit_token():
    ''' Get Oauth2 token for authentication on reddit

    Parameters
    ----------
    None

    Returns
    -------
    token
        token that authenticates the application for 1 hour
    '''
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
    print(f"\nMost popular r/wsb stock of the day: \n??? ???  {max(symbol_dict, key=symbol_dict.get)} ??? ???\n")
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
        list of dictionaries that contain all the relevant information regarding the stock
    '''
    results = []
    count = 0
    for post in post_listing['data']['children']:
        if stock in post['data']['title'] or stock in post['data']['selftext']:
            result = {'url': "https://reddit.com" + post['data']['permalink'], 'stock': stock,
            'upvote': post['data'].get('ups'), 'title': post['data']['title'],
            'post_text': post['data'].get('selftext'), 'flair': post['data'].get('link_flair_text'),
            'rank': count}
            count += 1
            results.append(result)
            # Writing to database
            create_query =\
                '''
                CREATE TABLE IF NOT EXISTS wsb_posts(url TEXT PRIMARY KEY, stock TEXT, upvote INT,
                title TEXT, post_text TEXT, flair TEXT, rank INT);
                '''
            insert_query =\
                '''
                INSERT OR IGNORE INTO wsb_posts VALUES(:url, :stock, :upvote, :title, :post_text, :flair, :rank);
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

def get_stock_info(stock):
    ''' Retrive real-time information on the most popular stock using Apha Vantage API

    Parameters
    ----------
    stock: string of stock symbol

    Returns
    -------
    list (if recrod found in db)
        list of sets that contain up-to-date stock information

    dict (if record not found in db)
        dictionary that contain up-to-date stock information
    '''
    today = datetime.datetime.today().strftime('%Y-%m-%d')
    sym_date = stock + '_' + str(today)

    connection = sqlite3.connect("wsb_synthesizer.sqlite")
    with connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM stocks WHERE sym_date = ?", (sym_date,))
        if cursor.fetchone():
            print("\nLoading stock information from cache ...\n")
            select_query = "SELECT * FROM stocks WHERE symbol = ?"
            result = cursor.execute(select_query, (stock,)).fetchall()
            return result
        else:
            secret = secrets.alpha_secret
            base_url = "https://www.alphavantage.co/query"
            params = {"function":"TIME_SERIES_DAILY_ADJUSTED", "symbol": stock, "apikey":secret}

            response = requests.get(base_url, params=params)
            data = response.json()
            date = data['Meta Data']['3. Last Refreshed'][:10]
            daily_adjusted = data['Time Series (Daily)'][date]
            open_p = daily_adjusted['1. open']
            high_p = daily_adjusted['2. high']
            low_p = daily_adjusted['3. low']
            close_p = daily_adjusted['4. close']
            dividend = daily_adjusted['7. dividend amount']

            params = {"function":"OVERVIEW", "symbol": stock, "apikey":secret}
            response = requests.get(base_url, params=params)
            data = response.json()
            company_desc = data['Description']
            result = {'sym_date': stock + "_" + date, 'symbol':stock, 'date':date, 'open':open_p, 'high':high_p, 'low': low_p, 'close': close_p,
            'dividend': dividend, 'description': company_desc}

            # Saving results to database for future caching
            create_query =\
                '''
                CREATE TABLE IF NOT EXISTS stocks(sym_date TEXT PRIMARY KEY, symbol TEXT, date TEXT, open REAL,
                high REAL, low REAL, close REAL, dividend REAL, description TEXT);
                '''
            insert_query =\
                '''
                INSERT OR IGNORE INTO stocks VALUES(:sym_date, :symbol, :date, :open, :high, :low, :close, :dividend, :description);
                '''

            try:
                connection = sqlite3.connect("wsb_synthesizer.sqlite")
                with connection:
                    cursor = connection.cursor()
                    cursor.execute(create_query)
                    cursor.execute(insert_query, result)
                    print('Writing stock information to database...\n')
            except sqlite3.Error as e:
                print(f"Error {e.args[0]}")

            return result


def show_stock_info(stock_info, stock):
    ''' Display market information, company description, and annual EPS graph
    on the most popular stock using Seaborn

    Parameters
    ----------
    stock_info: dictionary or list of sets containing information on a stock
    stock: string indicating the most popular stock

    Returns
    -------
    None
    '''

    secret = secrets.alpha_secret
    base_url = "https://www.alphavantage.co/query"
    params = {"function":"EARNINGS", "symbol": stock, "apikey":secret}

    response = requests.get(base_url, params=params)
    data = response.json()

    df = pd.DataFrame(data['annualEarnings'][:10])
    df = df.drop(0, axis=0)
    df['reportedEPS'] = df.reportedEPS.astype('float')

    f, ax = plt.subplots(1, figsize=(7, 4))
    ax.set_title("Annual Earnings of " + stock)
    plt.xticks(rotation=90)

    sns.barplot(data=df, x= df.fiscalDateEnding, y=df.reportedEPS, palette = sns.color_palette("PRGn", 10))
    plt.tight_layout()
    plt.show()

    # if stock info is cached
    # :sym_date, :symbol, :date, :open, :high, :low, :close, :dividend, :description
    if isinstance(stock_info, list):
        print(f"[{stock_info[-1][1]}] {stock_info[-1][2]} info:")
        print(f"Open: {stock_info[-1][3]}, High: {stock_info[-1][4]}, Low: {stock_info[-1][5]}, Close: {stock_info[-1][6]}, Dividend: {stock_info[-1][7]}")
        print(f"\n{stock_info[-1][-1]}")

    elif isinstance(stock_info, dict):
        print(f"[{stock_info['symbol']}] {stock_info['date']} info:")
        print(f"Open: {stock_info['open']}, High: {stock_info['high']}, Low: {stock_info['low']}, Close: {stock_info['close']}, Dividend: {stock_info['dividend']}")
        print(f"\n{stock_info['description']}\n")

def search_stock(stock, flair):
    ''' Display reddit posts on r/wsb that relates to the most popular stock of the day

    Parameters
    ----------
    stock: string that represents the most popular stock
    flair: string that specifies the type of post determined by subreddit flaire

    Returns
    -------
    list
        list of dictionaries that contain information about search results from reddit
    '''
    url = "https://oauth.reddit.com/r/wallstreetbets/search"
    params = {'t': 'week', 'limit': 100, 'q': stock, 'f': flair}
    res = requests.get(url, headers=headers, params=params)
    print(res.status_code)
    print('Searching from oauth.reddit.com ...\n')
    data = res.json()

    results = []
    for post in data['data']['children']:
        if post['data'].get('link_flair_text') == flair:
            result = {'url': "https://reddit.com" + post['data']['permalink'], 'stock': stock,
            'upvote': post['data'].get('ups'), 'title': post['data']['title'],
            'post_text': post['data'].get('selftext'), 'flair': post['data'].get('link_flair_text')
            }
            results.append(result)
    return results



if __name__ == "__main__":

    search_query = {'dd': 'DD', 'yolo': 'YOLO', 'tech':'Technical Analysis'}

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
    print('Welcome to r/wsb sythensizer!')
    res = input('Press Enter to see today\'s most talked about stock on r/wallstreetbets!\n')

    while str(res).lower() != 'exit':
        wsb_posts = get_cached_posts()
        t_start = datetime.datetime.now().timestamp()
        if wsb_posts is None:
            wsb_posts = get_posts(headers)
            POPULAR_STOCK = get_popular_stock(wsb_posts)
            relevant_posts = get_popular_posts(POPULAR_STOCK, wsb_posts)
            for post in relevant_posts:
                print(f"[{post['rank']}] {post['title']}")

            t_end = datetime.datetime.now().timestamp()
            print("\nload time without caching: ", (t_end - t_start) * 1000, "ms\n")
        else:
            for post in wsb_posts:
                print(f"[{post[-1]}] {post[3]}")

            t_end = datetime.datetime.now().timestamp()
            print("load time with caching: ", (t_end - t_start) * 1000, "ms\n")

        while res.lower() != 'exit':
            print("\n-------------------------------------------------------------------------")
            print('\ntype `info` for more stock info, or type flairs: `YOLO`, `DD`, `TECH` for other r/wsb posts this week.')
            print('YOLO = nonserious posts, DD = due diligence, TECH = technical analysis')
            print('or type the number of the reddit post you would like to view (opens a webpage)')
            res = input('`reload` to reload list, `exit` to exit\n\n')
            if res.isnumeric():
                print(f"Redirecting to reddit post.\n")
                if int(res) >= len(relevant_posts):
                    print("Please enter a number that is within the range of the displayed results!")
                    continue
                webbrowser.open(relevant_posts[int(res)]['url'])
            else:
                if res.lower() == 'info':
                    stock_info = get_stock_info(POPULAR_STOCK)
                    show_stock_info(stock_info, POPULAR_STOCK)
                elif res.lower() == 'reload':
                    break
                elif res.lower() in search_query.keys():
                    print(f"Searching for {res} r/wsb posts...\n")
                    searched_posts = search_stock(POPULAR_STOCK, search_query[str(res)])
                    for idx, post in enumerate(searched_posts):
                        print(f"[{idx}] {post['title']}")

                    while str(res).lower() != 'back' and str(res).lower() != 'exit':
                        print('\nEnter the number of post you would like to view')
                        res = input('`back` to return to previous step, `exit` to exit\n')
                        if res.isnumeric():
                            if int(res) >= len(searched_posts):
                                print("\nPlease enter a number that is within the range of the displayed results!")
                                continue
                            webbrowser.open(searched_posts[int(res)]['url'])
                        else:
                            print("\nPlease enter a valid number, or enter `back` to return to previous step")
                            continue
                elif res.lower() == 'exit':
                    break
                else:
                    print("\nInvalid input, please try again.\n")

    print('\nEnd of program, bye-bye investor, godspeed!')