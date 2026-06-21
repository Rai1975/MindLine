from src.backend.entry_analysis.object_recognition import analyze_sentence
from src.backend.entry_analysis.emotion_analysis import emotion_analysis, sentiment_analysis
from src.backend.entry_analysis.text_operations import pipeline
from src.backend.classes.stimulus import Stimulus
from src.backend.classes.object import Object
from src.backend.agents.filter_agent import filter_pairs

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
            new_obj = Object(token=noun)
            new_stim = Stimulus(new_obj.token, adj, sentence)
            stims.append(new_stim)

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

    return filter_pairs(stims)

if __name__ == "__main__":
    Big_Text = """
    Today I kept noticing how different everyone and everything felt. My teacher was patient, encouraging, and surprisingly funny. Shawn seemed quiet but thoughtful and kind. My friend Jacob was energetic, loud, and a little chaotic—but in a good way. Even I felt more confident, focused, and calm than usual. The classroom was bright and comfortable, the air cool and refreshing. My notes looked neat and organized for once. Lunch was warm, flavorful, and satisfying, and even the walk home felt peaceful and relaxing. It wasn’t about what happened today—it was more about how everything and everyone felt: steady, positive, and just… good.
    """

    Big_Text2 = """
    Today felt really productive in a totally different way. I finally got around to organizing my space, and it’s crazy how much better everything feels when things are clean and in order. I even tried cooking something new, and it actually turned out pretty good, which surprised me. Later on, I spent some time talking with a new coworker named Alex, and we just clicked right away—lots of laughs and easy conversation. It’s one of those days where everything just flows, and you end it thinking, yeah… this was a solid day.
    """

    result = final_pipeline(Big_Text)
    significant_pairs = result.significant_pairs
    for pair in significant_pairs:
            print(f'Key: {pair.entity}')
            print(f'Value: {pair.adjective}')
            print(f'sentence: {pair.sentence}')
            print(f'sen_sent: {pair.sentence_sentiment}')
            print(f'adj_sent: {pair.adjective_sentiment}')
            print(f'e1: {pair.emotion1}')
            print(f'e2: {pair.emotion2}')
            print(f'e3: {pair.emotion3}')
            print()