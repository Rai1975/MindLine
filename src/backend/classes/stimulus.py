class Stimulus:
    sentiment = ""
    emotion = ""
    noun = ""
    sentence = ""
    adjective = ""

    def __init__(self, noun, adjective, sentence):
        self.noun = noun
        self.adjective = adjective
        self.sentence = sentence
    
    def set_emotion(self, emotion):
        self.emotion = emotion
    
    def set_sentiment(self, sentence_sentiment, adj_sentiment):
        self.sentiment = (sentence_sentiment, adj_sentiment)

    def __str__(self):
        return f"{self.noun} : {self.adjective}\nSentence: {self.sentence}\nSentiment: {self.sentiment}\nEmotion: {self.emotion}"

    def get_json(self):
        return {
            "noun": self.noun,
            "adjective": self.adjective,
            "sentiment": self.sentiment,
            "emotion": self.emotion,
            "sentence": self.sentence
        }