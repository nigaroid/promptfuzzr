import os
import sys

import openai

if len(sys.argv) != 2:
    print("Usage: python probe_tool_calling.py <model-name>")
    sys.exit(1)

model_name = sys.argv[1]

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_COMPAT_API_KEY", "not-needed-for-local-router"),
    base_url=os.environ.get("OPENAI_COMPAT_BASE_URL", "http://localhost:20128/v1"),
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]

print(f"Probing model '{model_name}' at {client.base_url} ...")
response = client.chat.completions.create(
    model=model_name,
    max_tokens=256,
    messages=[{"role": "user", "content": "What's the weather in Paris right now?"}],
    tools=tools,
)

message = response.choices[0].message
print()
print("finish_reason:", response.choices[0].finish_reason)
print("message.content:", message.content)
print("message.tool_calls:", message.tool_calls)
print()

if message.tool_calls:
    print("RESULT: tool calling WORKS — safe to use OpenAICompatibleModelClient for the fuzzer.")
else:
    print("RESULT: no tool_calls in the response.")
    print("Either this model doesn't support tool calling, or omniroute isn't forwarding")
    print("the `tools` param correctly. action_outcome judging won't have anything to work")
    print("with against this model — the fuzzer will fall back to heuristic judging only,")
    print("which defeats the point of testing tool-calling-specific injections.")
