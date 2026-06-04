from src.backend.classes.object import Object
class Stimulus:
    sentiment = ""
    emotion = ""
    sentence = ""
    adjective = ""

    def __init__(self, noun, adjective, sentence):
        # Later implement logic to check db for duplicates and add ID
        self.noun = Object(token=noun)
        self.adjective = adjective
        self.sentence = sentence
    
    def set_emotion(self, emotion):
        self.emotion = emotion
    
    def set_sentiment(self, sentence_sentiment, adj_sentiment):
        self.sentiment = (sentence_sentiment, adj_sentiment)

    def __str__(self):
        return f"{self.noun.token} : {self.adjective}\nSentence: {self.sentence}\nSentiment: {self.sentiment}\nEmotion: {self.emotion}"

    def get_json(self):
        return {
            "noun": self.noun.token,
            "noun UUID": self.noun.getID(),
            "adjective": self.adjective,
            "sentiment": self.sentiment,
            "emotion": self.emotion,
            "sentence": self.sentence
        }