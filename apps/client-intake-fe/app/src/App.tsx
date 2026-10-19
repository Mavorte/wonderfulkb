import "./style.css";
import { useWonderful } from "@wonderful/app-sdk";
import { Alert, Box, PageLayout, PageLoader, Stack, Text } from "@wonderful/ui-base";
import { useEffect, useRef, useState } from "react";
import CaseSummary from "./components/CaseSummary";
import UploadPanel from "./components/UploadPanel";
import getIntakeHash from "./getIntakeHash";
import type { IntakeData } from "./types";

type State =
  | { status: "loading" }
  | { status: "error"; title: string; description: string }
  | { status: "ready"; data: IntakeData };

const INVALID_LINK = {
  title: "This link is not valid",
  description: "Please use the link from your latest message, or contact your KB advisor for a new one.",
};

function getErrorState(error: unknown): State {
  const message = error instanceof Error ? error.message : String(error);
  if (/401|expired/i.test(message)) {
    return {
      status: "error",
      title: "This link has expired",
      description: "Please contact your KB advisor and ask for a new link.",
    };
  }
  if (/404|invalid_link|case_not_found/i.test(message)) return { status: "error", ...INVALID_LINK };
  return {
    status: "error",
    title: "Something went wrong",
    description: "We could not load your case. Please try again in a few minutes.",
  };
}

export default function App() {
  const { api, track } = useWonderful();
  const [state, setState] = useState<State>({ status: "loading" });
  const hasTrackedOpen = useRef(false);

  useEffect(() => {
    if (!hasTrackedOpen.current) {
      hasTrackedOpen.current = true;
      track("intake_opened");
    }
    const hash = getIntakeHash();
    if (!hash) {
      setState({ status: "error", ...INVALID_LINK });
      return;
    }
    api
      .invokeFunction<IntakeData & { error?: string }>("client-intake/intake-get", {
        method: "POST",
        params: { hash },
      })
      .then((result) => {
        if (result?.error) setState(getErrorState(result.error));
        else setState({ status: "ready", data: result });
      })
      .catch((error) => setState(getErrorState(error)));
    // Load once per page open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app-root">
      <PageLayout maxWidth={960} padding={6}>
        <PageLayout.Header>
          <Stack gap={1}>
            <Text variant="heading-2">Documents for your financing</Text>
            <Text variant="body" color="secondary">
              Check your case details and upload the requested documents as PDF files.
            </Text>
          </Stack>
        </PageLayout.Header>
        <PageLayout.Content>
          {state.status === "loading" && (
            <Box direction="column" align="center" padding={8}>
              <PageLoader label="Loading your case" />
            </Box>
          )}
          {state.status === "error" && <Alert variant="error" title={state.title} description={state.description} />}
          {state.status === "ready" && (
            <Stack gap={4}>
              <CaseSummary data={state.data} />
              <UploadPanel data={state.data} />
            </Stack>
          )}
        </PageLayout.Content>
      </PageLayout>
    </div>
  );
}
