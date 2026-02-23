from src.backend.entry_analysis.object_recognition import analyze_sentence
from src.backend.entry_analysis.emotion_analysis import emotion_analysis, sentiment_analysis
from src.backend.entry_analysis.text_operations import pipeline

# Input for this is the text file stuff already read
def final_pipeline(text):
    # Returns list of cleaned and context-matched sentences
    cleaned_sentences = pipeline(text)

    print(cleaned_sentences)

    # Let's analyze each sentence and form pairs of
    # nouns and adjectives
    noun_adj_pairs = []

    for sentence in cleaned_sentences:
        noun_adj_pairs.append(analyze_sentence(sentence))

    print(noun_adj_pairs)

    # Let's do sentiment analysis on each of said noun-adj pairs
    # This is cool but I defo think we need to keep track of sentence
    # too. Maybe this needs it's own class.
    sentiments = {}
    sentence_counter = 0
    for sentence in noun_adj_pairs:
        for noun, adj in sentence:
            sent = sentiment_analysis(adj)[0]
            emo = emotion_analysis(adj)[0][0]
            if noun in sentiments.keys():
                sentiments[noun].append((sent, emo))
            else:
                sentiments[noun] = [(sent, emo)]

    print(sentiments)

    # Let's also run emotion analyses on these split sentences

if __name__ == "__main__":
    Big_Text = """
    Today was a great day man like I answered really well in all my classes
    and even got all my homework done on time. On top of that, I hit it off with this guy named Shawn
    and had a lot of fun. I think he's great dude and we'd make amazing friends like how can this day get any better.
    """

    final_pipeline(Big_Text)