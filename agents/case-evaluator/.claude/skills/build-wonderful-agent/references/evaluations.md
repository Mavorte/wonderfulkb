# Evaluations Reference

Read this reference before authoring, changing, or running evaluations.

## Definitions in the repository

- Scenarios live at `evals/scenarios/<slug>.json`.
- Batches live at `evals/batches/<slug>.json` and reference scenario slugs.
- The filename slug is the identifier passed to `wful eval`; keep it stable when changing an existing definition.

For a new definition, scaffold the scenario before any batch that references it:

```bash
wful scaffold scenario greeting_flow
wful scaffold batch smoke_suite --scenario greeting_flow
```

The scaffolder reads the agent mode from `config.json`, creates the matching scenario shape, and refuses to overwrite existing definitions. Every `--scenario` value passed to a batch must already exist. Replace the generated placeholders and give each scenario a narrow, observable expectation.

Run `wful agents schema` before changing an existing definition or extending a starter beyond its generated fields. It writes the scenario and batch schemas into `.wonderful/`; use those schemas for the current field set rather than copying a stale example. Use batches to group related scenarios. Do not include `.gitkeep` files in a batch.

## Widget evaluations

Widget evaluations are chat-only. Before authoring one, inspect `behavior.widgets.mode` in `config.json` for the version being evaluated:

- `disabled` or absent: do not add widget expectations, and do not change the policy unless the user asked you to enable widgets.
- `prebuilt_only`: scripted scenarios can verify widgets listed in `behavior.widgets.attached`.
- `prebuilt_and_generated`: scripted scenarios still verify attached widgets; simulations can also verify that the agent chooses generated components.

Use a scripted scenario when the conversation and attached widget are known. A widget assertion belongs on the turn that should render it. A `widget_submission` is the next user-input turn and targets the latest unconsumed widget:

```json
{
  "schema_version": 1,
  "name": "choose_pricing_plan",
  "description": "Shows the attached pricing widget and submits a plan.",
  "channel": "chat",
  "eval_type": "chat_eval",
  "instructions": {
    "mode": "turn_based",
    "genui": { "enabled": true },
    "turns": [
      {
        "user_message": "Show me the three pricing plans.",
        "assertions": [
          {
            "widget": {
              "rendered": true,
              "template_identifier": "pricing-plan-selector",
              "data_contains": { "plans": ["Basic", "Pro", "Enterprise"] },
              "actions_include": ["choose_plan"]
            }
          }
        ]
      },
      {
        "widget_submission": {
          "action": "choose_plan",
          "source_key": "pro_button",
          "values": { "plan": "pro" }
        },
        "agent_response": "Confirms that the customer selected the Pro plan."
      }
    ]
  }
}
```

Use `source_key` only when duplicate elements expose the same action. Values must match keys declared by the rendered action. The runtime derives the widget ID, catalog version, and presentation from the rendered widget; never hard-code them in the scenario. A widget can be submitted once, so render another widget before a later submission.

Use a simulation to test the model's widget choice, including generated components when the policy allows them:

```json
{
  "schema_version": 1,
  "name": "pricing_widget_selection",
  "description": "The agent selects the pricing experience and handles a silent choice.",
  "channel": "chat",
  "eval_type": "simulation_eval",
  "instructions": {
    "sim_version": 1,
    "genui": { "enabled": true },
    "caller": {
      "goal": "Compare the three plans and choose Pro.",
      "persona": "A customer who wants a concise comparison.",
      "speaks": "English",
      "locale": "en-US",
      "max_turns": 8,
      "widget_submissions": [
        {
          "target": {
            "template_identifier": "pricing-plan-selector"
          },
          "action": "choose_plan",
          "source_key": "pro_button",
          "values": { "plan": "pro" },
          "customer_presentation": "none"
        }
      ]
    },
    "expect": {
      "widgets_rendered": [
        {
          "rendered": true,
          "template_identifier": "pricing-plan-selector",
          "data_contains": { "plans": ["Basic", "Pro", "Enterprise"] }
        }
      ],
      "widgets_not_rendered": [
        { "rendered": true, "components_include": ["OrderConfirmation"] }
      ]
    }
  }
}
```

`widgets_rendered` and `widgets_not_rendered` test what the agent actually chose; they do not force a render. Use `components_include` for generated component selection and `template_identifier` for a known widget template.

Simulation submissions are ordered harness plans under `caller.widget_submissions`, not expectations. Each plan requires a `target` with `template_identifier`, `components_include`, or both. When the latest rendered widget matches, the harness sends exactly the authored action, optional source key, values, and customer presentation. The plan is not shown to the evaluated agent, and the caller model does not infer values from renderer code. Use `customer_presentation: "none"` for a silent submission or `"message"` for a visible customer message.

For a custom generated component whose action exists only in renderer code, author the action and values explicitly. Do not add component-specific inference to the scenario or eval runtime.

Scripted widget scenarios use `channel: "chat"` with `eval_type: "chat_eval"`. Widget simulations use `channel: "chat"` with `eval_type: "simulation_eval"`. `params_contain` checks named template parameters, or fields on exactly one targeted generated component; use `fallback_contains` for customer-readable fallback text and `data_contains` for structured widget data.

## Validate and run

```bash
wful validate
git push origin HEAD
wful validate --remote
SNAPSHOT_ID="$(wful agents snapshot)"
wful eval run <scenario-slug> --snapshot-id "$SNAPSHOT_ID"
wful eval run <batch-slug> --batch --snapshot-id "$SNAPSHOT_ID"
```

An evaluation runs server-side against the pinned snapshot, not uncommitted files. Use `wful eval status <run-id>` for an asynchronous run and `wful eval result <result-id> --show-all-turns` to inspect the verdict, transcript, rendered widgets, and widget submissions. Fix the agent or the evaluation definition based on the observed failure; do not weaken an evaluation merely to make it pass.
