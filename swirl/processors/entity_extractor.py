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

def extract_entities_by_type(text):
    doc = nlp(text)
    entities_by_type = {}

    for entity in doc.ents:
        entity_type = entity.label_
        entity_text = entity.text

        if entity_type not in entities_by_type:
            entities_by_type[entity_type] = []

        entities_by_type[entity_type].append(entity_text)

    return entities_by_type

FIELDS_TO_EXTRACT = ['title', 'body']

class EntityExtractingResultProcessor(ResultProcessor):

    type="EntityExtractingResultProcessorPostResultProcessor"

    def process(self):
        
        modified = 0
        for item in self.results:
            for field in FIELDS_TO_EXTRACT:
                if field in item:
                    if type(item[field]) == str:
                        detected_entities = extract_entities_by_type(item[field])
                        if detected_entities:
                            if not 'payload' in item:
                                item['payload'] = {}
                            if not 'entities' in item['payload']:
                                item['payload']['entities'] = []
                            item['payload']['entities'] = detected_entities

        self.processed_results = self.results
        self.modified = modified
        return self.modified
