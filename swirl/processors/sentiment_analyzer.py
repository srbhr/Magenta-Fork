'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''

from django.conf import settings

from swirl.processors.processor import *
from swirl.spacy import nlp

#############################################    

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def extract_sentiment(text):
    analyzer = SentimentIntensityAnalyzer()

    doc = nlp(text)
    sentences = [sent.text for sent in doc.sents]

    sentiment_scores = []
    for sentence in sentences:
        sentiment = analyzer.polarity_scores(sentence)
        sentiment_scores.append(sentiment['compound'])

    average_sentiment = sum(sentiment_scores) / len(sentiment_scores)

    return average_sentiment

FIELDS_TO_SCORE = ['title', 'body']

class SentimentAnalyzingResultProcessor(ResultProcessor):

    type="SentimentAnalyzingResultProcessorPostResultProcessor"

    def process(self):
        
        modified = 0
        for item in self.results:
            for field in FIELDS_TO_SCORE:
                if field in item:
                    if type(item[field]) == str:
                        average_sentiment = extract_sentiment(item[field])
                        if average_sentiment:
                            if not 'payload' in item:
                                item['payload'] = {}
                            if not 'sentiment' in item['payload']:
                                item['payload']['sentiment'] = {}
                            item['payload']['sentiment'][field] = average_sentiment

        self.processed_results = self.results
        self.modified = modified
        return self.modified
