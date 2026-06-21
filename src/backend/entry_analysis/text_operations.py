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

def pipeline(text):
    cleaned_text = response_cleaner(text)

    context_managed = context_manager(cleaned_text)

    parsed_sentences = sentence_parser(context_managed)

    return parsed_sentences

def textCleaner(text):
    cleaned_text = response_cleaner(text)
    context_managed = context_manager(text)

    return context_managed

if __name__ == "__main__":
    Big_Text2 = """
    Today felt really productive in a totally different way. I finally got around to organizing my space, and it’s crazy how much better everything feels when things are clean and in order. I even tried cooking something new, and it actually turned out pretty good, which surprised me. Later on, I spent some time talking with a new coworker named Alex, and we just clicked right away—lots of laughs and easy conversation. It’s one of those days where everything just flows, and you end it thinking, yeah… this was a solid day.
    """

    print(pipeline(Big_Text2))