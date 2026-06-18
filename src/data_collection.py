import tweepy
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import os
import configparser
import random
import string

class DataCollector:
    def __init__(self, config_file="config/twitter_config.ini"):
        self.data_dir = "data/raw"
        os.makedirs(self.data_dir, exist_ok=True)
        self.setup_twitter_api(config_file)
    
    def setup_twitter_api(self, config_file):
        """Set up Twitter API credentials"""
        print("🔧 Setting up Twitter API...")
        
        # Create config file if it doesn't exist
        if not os.path.exists(config_file):
            self.create_sample_config(config_file)
            print(f"⚠️  Please fill in your Twitter API credentials in {config_file}")
            self.api = None
            self.client = None
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(config_file)
            
            # Twitter API v2 credentials
            bearer_token = config.get('twitter', 'bearer_token', fallback=None)
            
            if bearer_token and "your_bearer_token_here" not in bearer_token and bearer_token.strip() != "":
                # For Twitter API v2
                self.client = tweepy.Client(bearer_token=bearer_token)
                self.api = None
                print("✅ Twitter API v2 client initialized")
            else:
                # Try v1.1 if v2 bearer_token is not present
                consumer_key = config.get('twitter', 'consumer_key', fallback=None)
                consumer_secret = config.get('twitter', 'consumer_secret', fallback=None)
                access_token = config.get('twitter', 'access_token', fallback=None)
                access_token_secret = config.get('twitter', 'access_token_secret', fallback=None)
                
                if (consumer_key and "your_consumer_key_here" not in consumer_key and consumer_key.strip() != "" and
                    consumer_secret and "your_consumer_secret_here" not in consumer_secret and
                    access_token and "your_access_token_here" not in access_token and
                    access_token_secret and "your_access_token_secret_here" not in access_token_secret):
                    
                    auth = tweepy.OAuth1UserHandler(
                        consumer_key, consumer_secret,
                        access_token, access_token_secret
                    )
                    self.api = tweepy.API(auth, wait_on_rate_limit=True)
                    self.client = None
                    print("✅ Twitter API v1.1 initialized")
                else:
                    print("⚠️  No valid Twitter credentials found in config. Will fall back to simulated mock data.")
                    self.api = None
                    self.client = None
                
        except Exception as e:
            print(f"❌ Error setting up Twitter API: {e}. Falling back to simulated mock data.")
            self.api = None
            self.client = None
    
    def create_sample_config(self, config_file):
        """Create a sample configuration file"""
        config = configparser.ConfigParser()
        
        config['twitter'] = {
            'bearer_token': 'your_bearer_token_here (for API v2)',
            'consumer_key': 'your_consumer_key_here',
            'consumer_secret': 'your_consumer_secret_here',
            'access_token': 'your_access_token_here',
            'access_token_secret': 'your_access_token_secret_here',
            'note': 'Use either bearer_token (v2) OR the four keys (v1.1)'
        }
        
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            config.write(f)
    
    def search_tweets_v2(self, query, max_tweets=100, days_back=7):
        """Search tweets using Twitter API v2"""
        if not self.client:
            print("❌ Twitter API v2 client not initialized")
            return []
        
        print(f"🔍 Searching tweets with query: {query}")
        
        # Calculate date range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        
        tweets = []
        next_token = None
        tweet_count = 0
        
        try:
            while tweet_count < max_tweets:
                # API v2 search
                response = self.client.search_recent_tweets(
                    query=query,
                    max_results=min(100, max_tweets - tweet_count),
                    start_time=start_time,
                    end_time=end_time,
                    tweet_fields=['created_at', 'public_metrics', 'author_id', 'context_annotations', 'entities'],
                    user_fields=['username', 'name', 'public_metrics'],
                    expansions='author_id',
                    next_token=next_token
                )
                
                if not response.data:
                    break
                
                # Create user lookup dictionary
                users = {user.id: user for user in response.includes.get('users', [])}
                
                for tweet in response.data:
                    user = users.get(tweet.author_id)
                    tweets.append({
                        'id': tweet.id,
                        'created_at': tweet.created_at,
                        'text': tweet.text,
                        'author_id': tweet.author_id,
                        'username': user.username if user else 'Unknown',
                        'author_name': user.name if user else 'Unknown',
                        'retweet_count': tweet.public_metrics['retweet_count'],
                        'like_count': tweet.public_metrics['like_count'],
                        'reply_count': tweet.public_metrics['reply_count'],
                        'quote_count': tweet.public_metrics['quote_count'],
                        'impression_count': tweet.public_metrics['impression_count'],
                        'hashtags': [tag['tag'] for tag in tweet.entities.get('hashtags', [])] if hasattr(tweet, 'entities') and tweet.entities else [],
                        'mentions': [mention['username'] for mention in tweet.entities.get('mentions', [])] if hasattr(tweet, 'entities') and tweet.entities else [],
                        'urls': [url['expanded_url'] for url in tweet.entities.get('urls', [])] if hasattr(tweet, 'entities') and tweet.entities else []
                    })
                    
                    tweet_count += 1
                    if tweet_count >= max_tweets:
                        break
                
                # Check if there are more results
                next_token = response.meta.get('next_token')
                if not next_token:
                    break
                    
                # Rate limiting respect
                time.sleep(1)
                
        except tweepy.TooManyRequests:
            print("⏳ Rate limit exceeded. Waiting for 15 minutes...")
            time.sleep(15 * 60)
        except Exception as e:
            print(f"❌ Error searching tweets: {e}")
        
        return tweets
    
    def search_tweets_v1(self, query, max_tweets=100, days_back=7):
        """Search tweets using Twitter API v1.1"""
        if not self.api:
            print("❌ Twitter API v1.1 not initialized")
            return []
        
        print(f"🔍 Searching tweets with query: {query}")
        
        tweets = []
        
        try:
            for tweet in tweepy.Cursor(
                self.api.search_tweets,
                q=query,
                lang='en',
                tweet_mode='extended',
                count=min(100, max_tweets)
            ).items(max_tweets):
                
                tweets.append({
                    'id': tweet.id,
                    'created_at': tweet.created_at,
                    'text': tweet.full_text,
                    'username': tweet.user.screen_name,
                    'author_name': tweet.user.name,
                    'retweet_count': tweet.retweet_count,
                    'like_count': tweet.favorite_count,
                    'reply_count': 0,  # Not directly available in v1.1
                    'quote_count': 0,  # Not directly available in v1.1
                    'impression_count': 0,  # Not available in v1.1
                    'hashtags': [hashtag['text'] for hashtag in tweet.entities.get('hashtags', [])],
                    'mentions': [mention['screen_name'] for mention in tweet.entities.get('user_mentions', [])],
                    'urls': [url['expanded_url'] for url in tweet.entities.get('urls', [])],
                    'user_followers': tweet.user.followers_count,
                    'user_friends': tweet.user.friends_count,
                    'user_statuses': tweet.user.statuses_count
                })
                
        except tweepy.RateLimitError:
            print("⏳ Rate limit exceeded. Please wait...")
        except Exception as e:
            print(f"❌ Error searching tweets: {e}")
        
        return tweets
    
    def scrape_twitter_data(self, queries, days_back=7, max_tweets_per_query=200):
        """Scrape tweets based on queries using Tweepy"""
        print("🔍 Collecting Twitter data using Tweepy...")
        
        all_tweets = []
        
        # Check if API configured
        has_api = (hasattr(self, 'client') and self.client) or (hasattr(self, 'api') and self.api)
        if not has_api:
            print("⚠️  No Twitter API keys configured. Falling back to simulated data.")
            return self.generate_mock_twitter_data(queries, max_tweets_per_query, days_back)
            
        for query in queries:
            print(f"📝 Searching for: {query}")
            
            # Try API v2 first, then fall back to v1.1
            try:
                if hasattr(self, 'client') and self.client:
                    tweets = self.search_tweets_v2(query, max_tweets_per_query, days_back)
                elif hasattr(self, 'api') and self.api:
                    tweets = self.search_tweets_v1(query, max_tweets_per_query, days_back)
                else:
                    tweets = []
            except Exception as e:
                print(f"❌ Error during Twitter search for '{query}': {e}")
                tweets = []
            
            if tweets:
                query_tweets_df = pd.DataFrame(tweets)
                query_tweets_df['search_query'] = query
                all_tweets.append(query_tweets_df)
                print(f"✅ Found {len(tweets)} tweets for query: {query}")
            else:
                print(f"❌ No tweets found for query: {query}")
            
            # Be respectful to API limits
            time.sleep(2)
        
        if all_tweets:
            final_df = pd.concat(all_tweets, ignore_index=True)
            
            # Convert created_at to datetime if it's string
            if 'created_at' in final_df.columns:
                final_df['created_at'] = pd.to_datetime(final_df['created_at'])
            
            filename = f"{self.data_dir}/tweets_tweepy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            final_df.to_csv(filename, index=False)
            print(f"💾 Saved {len(final_df)} tweets to {filename}")
            return final_df
        else:
            print("⚠️  No tweets collected from API. Falling back to simulated data.")
            return self.generate_mock_twitter_data(queries, max_tweets_per_query, days_back)
    
    def get_trending_topics(self, woied=1):
        """Get trending topics for a specific location (WOEID)"""
        if not hasattr(self, 'api') or not self.api:
            print("❌ Twitter API v1.1 required for trending topics")
            return []
        
        try:
            trends = self.api.get_place_trends(woied)
            trending_list = []
            
            for trend in trends[0]['trends'][:20]:  # Top 20 trends
                trending_list.append({
                    'name': trend['name'],
                    'url': trend['url'],
                    'tweet_volume': trend.get('tweet_volume', 0),
                    'query': trend['query']
                })
            
            return trending_list
            
        except Exception as e:
            print(f"❌ Error getting trending topics: {e}")
            return []
    
    def get_user_timeline(self, username, count=100):
        """Get tweets from a specific user's timeline"""
        if not hasattr(self, 'api') or not self.api:
            print("❌ Twitter API required for user timeline")
            return []
        
        try:
            tweets = []
            for tweet in tweepy.Cursor(
                self.api.user_timeline,
                screen_name=username,
                count=count,
                tweet_mode='extended'
            ).items(count):
                
                tweets.append({
                    'id': tweet.id,
                    'created_at': tweet.created_at,
                    'text': tweet.full_text,
                    'retweet_count': tweet.retweet_count,
                    'like_count': tweet.favorite_count,
                    'is_retweet': hasattr(tweet, 'retweeted_status')
                })
            
            return tweets
            
        except Exception as e:
            print(f"❌ Error getting user timeline: {e}")
            return []
    
    def scrape_reddit_data(self, subreddits, days_back=7, max_posts=500):
        """Scrape Reddit posts from specified subreddits"""
        print("🔍 Collecting Reddit data...")
        
        all_posts = []
        
        for subreddit in subreddits:
            print(f"Scraping r/{subreddit}...")
            
            try:
                # Using Pushshift API
                url = "https://api.pushshift.io/reddit/search/submission/"
                params = {
                    'subreddit': subreddit,
                    'size': min(100, max_posts),
                    'after': f'{days_back}d',
                    'sort_type': 'created_utc',
                    'sort': 'desc'
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()['data']
                    
                    for post in data:
                        all_posts.append([
                            datetime.fromtimestamp(post['created_utc']),
                            post.get('title', ''),
                            post.get('selftext', ''),
                            post.get('subreddit', ''),
                            post.get('score', 0),
                            post.get('num_comments', 0),
                            post.get('upvote_ratio', 0),
                            post.get('author', ''),
                            post.get('url', ''),
                            post.get('permalink', '')
                        ])
                else:
                    print(f"Pushshift status code: {response.status_code}. Using simulation fallback.")
                
                time.sleep(1)  # Be respectful to the API
                
            except Exception as e:
                print(f"Error scraping r/{subreddit}: {e}. Will use simulation fallback.")
                continue
        
        if all_posts:
            reddit_df = pd.DataFrame(all_posts, columns=[
                'Date', 'Title', 'Content', 'Subreddit', 'Score', 
                'Comments', 'Upvote_Ratio', 'Author', 'URL', 'Permalink'
            ])
            filename = f"{self.data_dir}/reddit_posts_{datetime.now().strftime('%Y%m%d')}.csv"
            reddit_df.to_csv(filename, index=False)
            print(f"✅ Saved {len(reddit_df)} Reddit posts to {filename}")
            return reddit_df
        else:
            print("⚠️  No Reddit posts collected from Pushshift. Falling back to simulated data.")
            return self.generate_mock_reddit_data(subreddits, max_posts, days_back)

    def generate_mock_twitter_data(self, queries, max_tweets_per_query=200, days_back=7):
        """Generate realistic simulated Twitter data for testing/demo when API keys are missing"""
        print("💡 Generating simulated Twitter data for demonstration...")
        
        # Sample text pieces for each query to make the generated data realistic
        templates = {
            "AI OR ChatGPT OR OpenAI": [
                "Just had a mind-blowing session with ChatGPT! The reasoning capabilities are getting insanely good. #AI #Tech",
                "Is anyone else worried about the rapid progress of OpenAI? GPT-5 is going to change everything. #ArtificialIntelligence",
                "Using AI to refactor code is a game changer. Saved me 3 hours of debugging today. #programming #ChatGPT",
                "We need clear regulations for generative AI. The misinformation potential is scary. #AI #Ethics",
                "OpenAI's new model update makes coding assistance so much smoother. Loving the speed! #OpenAI #developer",
                "Can AI truly replace creative writers? Some ChatGPT outputs feel quite generic, but others are brilliant. #AI #Creativity",
                "Building a new SaaS using OpenAI APIs. The developer tools and documentation are top notch.",
                "AI is not a bubble; it is the infrastructure for the next century of software. #MachineLearning #OpenAI",
                "Unpopular opinion: ChatGPT is making developers lazy. We need to understand the fundamentals first.",
                "Struggling with OpenAI API rate limits today. Everyone must be building something cool!"
            ],
            "machine learning OR deep learning": [
                "Deep learning models are achieving incredible accuracy in medical image segmentation. Huge win for healthcare! #ML",
                "Fascinated by transformers and self-attention mechanisms. The math behind deep learning is beautiful. #MachineLearning",
                "Just published my first research paper on reinforcement learning! Huge milestone. #DeepLearning #Research",
                "What is the best way to get started with machine learning in 2026? PyTorch or TensorFlow? #ML #DataScience",
                "Training a convolutional neural network (CNN) on my laptop and the fans are ready for takeoff 🚀 #DeepLearning",
                "Bias in machine learning datasets is a major issue. Garbarge in, garbage out. #EthicsInAI #DataScience",
                "Supervised learning vs unsupervised learning - which one is more promising for real-world business problems? #ML",
                "Deploying deep learning models to edge devices is extremely challenging but super rewarding. #IoT #Tech",
                "Gradient descent is still the magic engine behind all these amazing breakthroughs in ML. #Mathematics",
                "Highly recommend the new machine learning specialization course. Extremely clear explanations of backprop!"
            ],
            "data science OR analytics": [
                "A clean dataset is worth more than a fancy model. Spend time on data cleaning! #DataScience #DataAnalytics",
                "Data analyst vs Data scientist - the industry still struggles to define the difference clearly. #Career",
                "Loving Plotly for interactive dashboard visualizations. It makes data storytelling so much better. #DataAnalytics",
                "Sql is still the most important tool in a data scientist's toolkit. Change my mind. #SQL #DataScience",
                "Using pandas and numpy for data analysis is so intuitive. Python has won the data science war.",
                "A/B testing is where the rubber meets the road in analytics. Don't rely on intuition, test it! #Analytics",
                "Just built a customer churn prediction dashboard. The insights are already driving sales strategy. #DataAnalytics",
                "Data privacy regulations like GDPR make big data analytics much more complicated but necessary.",
                "Seaborn makes beautiful static plots, but dynamic dashboards need Plotly or Streamlit. #Python #DataViz",
                "Remember: correlation does not imply causation! Always be careful when analyzing trends. #DataScience"
            ]
        }
        
        # Fallback templates if query doesn't match exactly
        default_templates = [
            "Exciting developments in technology today! The pace of change is incredible. #Tech #Innovation",
            "This new software release is full of bugs. Very frustrating. #SoftwareDevelopment",
            "Just reading about the future of computing. Quantum systems look promising.",
            "Attending a virtual conference on tech trends. Some great insights on analytics.",
            "Coding late tonight. Coffee is my co-pilot. #DeveloperLife"
        ]
        
        usernames = ["tech_guru", "code_ninja", "data_wizard", "ai_pioneer", "cyber_explorer", "byte_sized", "stack_dev", "algo_rider", "cloud_walker", "neural_net"]
        names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Casey", "Jamie", "Riley", "Robin", "Pat"]
        
        all_tweets = []
        
        for query in queries:
            query_templates = templates.get(query, default_templates)
            num_tweets = min(max_tweets_per_query, random.randint(30, 80)) # Generate a reasonable number of tweets
            
            for i in range(num_tweets):
                # Distribute dates over the days_back range
                hours_ago = random.uniform(0, days_back * 24)
                created_at = datetime.utcnow() - timedelta(hours=hours_ago)
                
                text = random.choice(query_templates)
                # Add some randomness to text to avoid duplicates
                if random.random() > 0.5:
                    text += f" (Reviewing this in {created_at.strftime('%B %Y')})"
                
                # Extract hashtags from text
                hashtags = [word[1:].lower().translate(str.maketrans('', '', string.punctuation)) 
                            for word in text.split() if word.startswith('#')]
                
                likes = int(random.lognormvariate(3, 1))
                retweets = int(likes * random.uniform(0.1, 0.4))
                replies = int(likes * random.uniform(0.05, 0.2))
                
                idx = random.randint(0, len(usernames)-1)
                
                all_tweets.append({
                    'id': 1000000000000000000 + random.randint(100000000000, 999999999999),
                    'created_at': created_at,
                    'text': text,
                    'author_id': 2000000000 + random.randint(100000, 999999),
                    'username': usernames[idx],
                    'author_name': f"{names[idx]} {random.choice(['S.', 'J.', 'M.', 'L.', 'K.'])}",
                    'retweet_count': retweets,
                    'like_count': likes,
                    'reply_count': replies,
                    'quote_count': int(retweets * random.uniform(0.05, 0.2)),
                    'impression_count': likes * random.randint(5, 20),
                    'hashtags': hashtags,
                    'mentions': [random.choice(usernames)] if random.random() > 0.7 else [],
                    'urls': ['https://example.com/tech-news'] if random.random() > 0.8 else []
                })
                
        df = pd.DataFrame(all_tweets)
        if not df.empty:
            df['search_query'] = queries[0] if len(queries) == 1 else "combined_queries"
            # Sort by created_at
            df = df.sort_values(by='created_at').reset_index(drop=True)
            
            # Save raw simulated data
            filename = f"{self.data_dir}/tweets_simulated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False)
            print(f"💾 Saved {len(df)} simulated tweets to {filename}")
            return df
        return pd.DataFrame()

    def generate_mock_reddit_data(self, subreddits, max_posts=500, days_back=7):
        """Generate realistic simulated Reddit data for testing/demo when Pushshift is unavailable"""
        print("💡 Generating simulated Reddit data for demonstration...")
        
        templates = {
            "technology": [
                ("Is this the end of traditional smartphones?", "With VR, AR, and neural interfaces advancing so quickly, do you think traditional smartphones will be obsolete in the next 10 years? Let's discuss."),
                ("Quantum computing startup claims major breakthrough in error correction", "They announced they reached a stable logical qubit. If true, this could accelerate commercial quantum systems by five years. What do you think?"),
                ("The rise of decentralized social media platforms", "I've been playing around with Mastodon, Bluesky, and Farcaster. They feel very different from Twitter. Will decentralization become mainstream?"),
                ("EU passes comprehensive regulations on smart devices privacy", "New laws require all smart home devices to keep user data locally by default unless explicit permission is given. Huge win for consumers.")
            ],
            "artificial": [
                ("Artificial General Intelligence (AGI) prediction thread", "When do you think we will achieve true AGI? Some experts say 3 years, others say 20. What is your realistic timeline and why?"),
                ("AI alignment problem is being ignored by big tech", "It seems companies are in a race to build the biggest models without ensuring safety and alignment. Are we heading towards a disaster?"),
                ("How artificial neural networks are mimicking human brain visual cortex", "Interesting research paper showing that the latest vision transformers learn representations very similar to mammalian visual processing.")
            ],
            "MachineLearning": [
                ("Tips for training models with limited data?", "I only have about 500 labeled images for a specific classification task. What augmentation techniques and pre-trained models work best?"),
                ("PyTorch 2.0 compile feature - hands on experiences?", "Has anyone successfully deployed models compiled with PyTorch 2.0 in production? Did you see the promised 1.5x-2x speedups?"),
                ("Reinforcement Learning from Human Feedback (RLHF) vs DPO", "Direct Preference Optimization seems much simpler to train than RLHF. Is there any reason to still use PPO for LLM alignment?"),
                ("Why deep learning models generalize so well despite overparameterization", "A discussion on the double descent phenomenon and the implicit regularization of SGD in high dimensions.")
            ],
            "datascience": [
                ("How to transition from software engineering to data science?", "I have 5 years of experience in Java backend development. How do I build a portfolio to land a data science job?"),
                ("What database is best for storing large unstructured text data for NLP?", "We are building an email analysis tool and expect millions of documents. Should we use PostgreSQL with pgvector, or Elasticsearch?"),
                ("Does your company actually use machine learning in production?", "Or is it just a bunch of Excel spreadsheets and simple SQL queries disguised as AI? Be honest!"),
                ("Best practices for tracking model lineage and metrics", "We are setting up MLflow but finding the setup a bit clunky. What alternatives (like Weights & Biases or Comet) do you recommend?")
            ],
            "programming": [
                ("Why functional programming hasn't taken over the industry", "Languages like Haskell and Clojure are elegant, but most production systems are still object-oriented or procedural. Why?"),
                ("Is coding still a viable career for the next 20 years?", "With AI coding assistants getting better at generating whole apps, what should new computer science graduates focus on to stay valuable?"),
                ("The case against microservices: when monoliths are better", "A detailed write-up on how early microservice adoption can kill startups due to operational complexity and overhead."),
                ("How to write maintainable code as a solo developer", "What are your rules of thumb? I write unit tests for core business logic but skip visual regression tests. What about you?")
            ]
        }
        
        default_templates = [
            ("Interesting tech discussion", "What are you working on this week? Share your projects, blockers, and wins below!"),
            ("Help with a coding error", "I keep getting a division by zero error in my loop but I checked all inputs. Any ideas what might cause this?"),
            ("Review of a new programming library", "I tested this library for web scraping and it is 10 times faster than BeautifulSoup. Check out my benchmark.")
        ]
        
        authors = ["reddit_user_1", "data_junkie", "tech_enthusiast", "coding_geek", "ai_researcher", "matrix_neo", "py_dev", "stat_pro", "science_guy", "byte_me"]
        
        all_posts = []
        
        for subreddit in subreddits:
            sub_templates = templates.get(subreddit, default_templates)
            # Generate a reasonable number of posts
            num_posts = min(max_posts, random.randint(20, 50))
            
            for i in range(num_posts):
                hours_ago = random.uniform(0, days_back * 24)
                created_utc = datetime.utcnow() - timedelta(hours=hours_ago)
                
                title, content = random.choice(sub_templates)
                # Add some randomness
                if random.random() > 0.5:
                    title += f" (Discussing in {subreddit})"
                
                score = int(random.lognormvariate(4, 1.2))
                comments = int(score * random.uniform(0.1, 0.5))
                upvote_ratio = round(random.uniform(0.75, 0.99), 2)
                
                author = random.choice(authors)
                
                all_posts.append([
                    created_utc,
                    title,
                    content,
                    subreddit,
                    score,
                    comments,
                    upvote_ratio,
                    author,
                    f"https://www.reddit.com/r/{subreddit}/comments/mock_post_id",
                    f"/r/{subreddit}/comments/mock_post_id"
                ])
                
        reddit_df = pd.DataFrame(all_posts, columns=[
            'Date', 'Title', 'Content', 'Subreddit', 'Score', 
            'Comments', 'Upvote_Ratio', 'Author', 'URL', 'Permalink'
        ])
        
        if not reddit_df.empty:
            # Sort by Date
            reddit_df = reddit_df.sort_values(by='Date').reset_index(drop=True)
            filename = f"{self.data_dir}/reddit_posts_simulated_{datetime.now().strftime('%Y%m%d')}.csv"
            reddit_df.to_csv(filename, index=False)
            print(f"✅ Saved {len(reddit_df)} simulated Reddit posts to {filename}")
            return reddit_df
            
        return pd.DataFrame()

# Example usage and testing
if __name__ == "__main__":
    collector = DataCollector()
    
    # Test Twitter data collection
    if hasattr(collector, 'client') or hasattr(collector, 'api'):
        twitter_df = collector.scrape_twitter_data(
            queries=["AI OR ChatGPT", "machine learning", "data science"],
            days_back=3,
            max_tweets_per_query=50
        )
        
        # Test trending topics (if API v1.1 is available)
        if hasattr(collector, 'api') and collector.api:
            trends = collector.get_trending_topics(woied=1)  # Worldwide trends
            if trends:
                print("\n🔥 Trending Topics:")
                for i, trend in enumerate(trends[:10], 1):
                    volume = f" ({trend['tweet_volume']} tweets)" if trend['tweet_volume'] else ""
                    print(f"{i}. {trend['name']}{volume}")
    
    # Test Reddit data collection
    reddit_df = collector.scrape_reddit_data(
        subreddits=["technology", "MachineLearning"],
        days_back=3,
        max_posts=100
    )