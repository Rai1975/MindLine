from src.backend.entry_analysis.object_recognition import analyze_sentence
from src.backend.entry_analysis.emotion_analysis import emotion_analysis, sentiment_analysis
from src.backend.entry_analysis.text_operations import pipeline
from src.backend.classes.stimulus import Stimulus

# Input for this is the text file stuff already read
def final_pipeline(text):
    # Returns list of cleaned and context-matched sentences
    cleaned_sentences = pipeline(text)

    # print(cleaned_sentences)

    # Let's analyze each sentence and form pairs of
    # nouns and adjectives
    stims = []

    for sentence in cleaned_sentences:
        sentence_pairs = analyze_sentence(sentence)
        for noun, adj in sentence_pairs:
           new_stim = Stimulus(noun, adj, sentence)
           stims.append(new_stim)

    # Let's do sentiment analysis on each of said noun-adj pairs
    # This is cool but I defo think we need to keep track of sentence
    # too. Maybe this needs it's own class.

    # And also, if there's no adjectives in the sentence
    # We gotta just straight up do sentiment/emotion analysis on
    # said sentence and analyze

    # Maybe set the sentimet as a pair of (sentence, adjective)
    for stim in stims:
        adj_sentiment = sentiment_analysis(stim.adjective)
        sen_sentiment = sentiment_analysis(stim.sentence)
        emotion = emotion_analysis(stim.sentence)
        stim.set_sentiment(sen_sentiment, adj_sentiment)
        stim.set_emotion(emotion)

        print(stim, end='\n\n')

    # sentiments = {}
    # for sentence in stims:
    #     for noun, adj in sentence:
    #         sent = sentiment_analysis(adj)[0]
    #         emo = emotion_analysis(adj)[0][0]
    #         if noun in sentiments.keys():
    #             sentiments[noun].append((sent, emo))
    #         else:
    #             sentiments[noun] = [(sent, emo)]

    # for stim in stims:
    #     print(stim)
    # print(sentiments)

if __name__ == "__main__":
    Big_Text = """
    Today I kept noticing how different everyone and everything felt. My teacher was patient, encouraging, and surprisingly funny. Shawn seemed quiet but thoughtful and kind. My friend Jacob was energetic, loud, and a little chaotic—but in a good way. Even I felt more confident, focused, and calm than usual. The classroom was bright and comfortable, the air cool and refreshing. My notes looked neat and organized for once. Lunch was warm, flavorful, and satisfying, and even the walk home felt peaceful and relaxing. It wasn’t about what happened today—it was more about how everything and everyone felt: steady, positive, and just… good.
    """

    final_pipeline(Big_Text)