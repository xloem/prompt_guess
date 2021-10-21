#!/usr/bin/env python3
import codesynth, prompt_guess
import sys

backend = codesynth.eleuther_demo()
prompt = prompt_guess.Prompts(backend)

print('''
Input/Output Prompt Learner

Give an empty input to change the last output.

A prompt is formed of every output provided by the user.  The prompt is not saved.
''')

while True:
    try:
        user_input = input(prompt.input_prefix)

        if not len(user_input):
            user_input = last_user_input
            sys.stdout.write(prompt.input_prefix + user_input + prompt.input_postfix)
            raise RuntimeError

        prompt_output = prompt.guess(user_input, False)
        sys.stdout.write(prompt.output_prefix + prompt_output + prompt.output_postfix)

    except RuntimeError:
        user_output = input(prompt.output_prefix)
        prompt.add(user_input, user_output)

    last_user_input = user_input
