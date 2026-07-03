"""AgentLens quickstart — the 3-line integration target (docs/04-SDK-DESIGN.md §1).

Not functional yet: trace/patchers ship in roadmap Weeks 2-3; this example is
wired up end-to-end in Week 2 (docs/05-ROADMAP.md).
"""

# import agentlens
#
# agentlens.init(api_key="al_...", project="fittrack-recipes",
#                endpoint="https://lens.myserver.com")  # 1
#
# @agentlens.trace(name="generate_recipe", span_type="agent")   # 2
# def generate_recipe(user_profile: dict) -> dict:
#     ...
#
# agentlens.patch_anthropic()  # 3 — every Anthropic call now auto-traced
