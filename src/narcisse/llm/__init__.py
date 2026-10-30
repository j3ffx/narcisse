"""The optional assistant: an LLM the user chose, asked about a trace only when they ask.

Nothing here is needed for Narcisse to work. A provider takes a task (its instructions and the
JSON shape of its answer) and the text to send; what it answers is stored as an annotation that
changes nothing until the user accepts it.
"""
