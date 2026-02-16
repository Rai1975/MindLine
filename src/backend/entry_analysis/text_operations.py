from openai import OpenAI
import re
import spacy
from src.backend.config import OPENAI_API_KEY

# Loading spacy module on app start
spacy_model = spacy.load("en_core_web_sm")

# Helper function for openai calls
def chat_response(system_prompt, input):
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    output = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": f"Transcript: {input}"}
        ]
    )

    return output.choices[0].message.content

def response_cleaner(response):
    SYSTEM_PROMPT = """
    You are an intelligent agent tasked with cleaning up grammatical errors in spoken words. You will
    be given a transcript from spoken text which you will have to clean up into correct grammar.

    You will only return the cleaned text as your output.

    YOU MUST NOT CHANGE THE SENTENCE STRUCTURE OR THE SEMANTIC MEANING OF THE SENTENCES.
    """
    return chat_response(SYSTEM_PROMPT, response)

def context_manager(text):
    SYSTEM_PROMPT = """
    You are an intelligent agent tasked with keeping context of the paragraph in each sentence. You will
    be given a piece of text within which you will identify objects, and make sure
    references to those objects are explicit.

    For example:
    Input: "I met this guy named Shawn. He was really cool"
    Output: "I met this guy named Shawn. Shawn was really cool"

    You will only return the cleaned text as your output.

    YOU MUST NOT CHANGE THE SENTENCE STRUCTURE OR THE SEMANTIC MEANING OF THE SENTENCES.
    """

    return chat_response(SYSTEM_PROMPT, text)

# Splits paragraphs into separate sentences
def sentence_parser(text):
    return re.split(r'(?<=[.!?]) +', text)

# Actually idk about this, what about complex sentences?
# We can't just give an object a sentiment based on the sentence sentiment
def object_recognition(sentences):
    proper_nouns = []
    nouns = []

    for text in sentences:
        doc = spacy_model(text)

        sentence_propns = []
        sentence_nouns = []
        for token in doc:
            if token.pos_ == "PROPN":
                sentence_propns.append(token.text)

            elif token.pos_ == "NOUN":
                sentence_nouns.append(token.text)

        proper_nouns.append(sentence_propns)
        nouns.append(sentence_nouns)


    return {"NOUN": nouns, "PROPN": proper_nouns}


if __name__ == "__main__":
        Big_Text = """
        Today was a great day man like I answered really well in all my classes
        and even got all my homework done on time. On top of that, I hit it off with this guy named Shawn
        and had a lot of fun. I think he's great dude and we'd make amazing friends like how can this day get any better.
        """

        cleaned_response = response_cleaner(Big_Text)
        print(cleaned_response)
        print("---")

        final_text = context_manager(cleaned_response)
        print(final_text)
        print('---')

        sentences = sentence_parser(final_text)
        print(sentences)
        print('---')

        obs = object_recognition(sentences)
        print(obs)
        print('---')