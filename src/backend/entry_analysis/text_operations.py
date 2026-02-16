from openai import OpenAI
import re
from src.backend.config import OPENAI_API_KEY

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

        print(sentence_parser(final_text))