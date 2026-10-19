// Register a Client Intake link for the persisted OCR case. Calls without
// case_id retain the original standalone mocked case-creation behavior.
import createCaseLink from "./createCaseLink.ts";

async function userFunction(context) {
  return createCaseLink(context);
}
