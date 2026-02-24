from transformers import pipeline

sentiment_model = pipeline("text-classification", model="tabularisai/multilingual-sentiment-analysis", return_all_scores=False)
emotion_model = pipeline(task="text-classification", model="SamLowe/roberta-base-go_emotions", top_k=None)

# Returns the sentiment and confidence score of overall sentiment
def sentiment_analysis(sentence):
    result = sentiment_model(sentence)[0]

    result = (result.get('label'), result.get('score'))

    return result

# Returns the top 3 emotions from the sentence given to it
def emotion_analysis(sentence):
    model_outputs = emotion_model([sentence])[0]

    result = []

    for item in model_outputs[:3]:
        result.append((item.get('label'), item.get('score')))

    return result

if __name__ == "__main__":
    sentence = 'Later on, I spent some time talking with a new coworker named Alex'
    sentence_2 = 'and Alex and I just clicked right away—lots of laughs and easy conversation.'

    print(sentiment_analysis(sentence))
    print('---')
    print(emotion_analysis(sentence))
    print('---')
    print('---')
    print(sentiment_analysis(sentence_2))
    print('---')
    print(emotion_analysis(sentence_2))