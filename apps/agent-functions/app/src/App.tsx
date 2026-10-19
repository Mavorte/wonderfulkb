import "./style.css";
import { Card, PageLayout, Stack, Text } from "@wonderful/ui-base";

// Layout note: `Box` defaults to `direction="row"`. Use `Stack` for vertical
// stacks, and pass `direction` explicitly whenever you do reach for `Box` — a
// bare `<Box>` lays its children out sideways. `pnpm build` enforces this.
export default function App() {
  return (
    <div className="app-root">
      <PageLayout maxWidth={1200} padding={6}>
        <PageLayout.Header>
          <Text variant="heading-2">Wonderful App Starter</Text>
        </PageLayout.Header>
        <PageLayout.Content>
          <Stack gap={4}>
            <Text variant="body">
              This app is running from <code>src/App.tsx</code>. Replace this file with your feature UI.
            </Text>
            <Card padding={4}>
              <Stack gap={2}>
                <Text variant="body-sm" color="secondary">
                  Edit <code>src/App.tsx</code> for app content.
                </Text>
                <Text variant="body-sm" color="secondary">
                  Keep the default export from <code>src/index.ts</code>.
                </Text>
                <Text variant="body-sm" color="secondary">
                  Run <code>pnpm build &amp;&amp; pnpm package</code> before upload.
                </Text>
              </Stack>
            </Card>
          </Stack>
        </PageLayout.Content>
      </PageLayout>
    </div>
  );
}
