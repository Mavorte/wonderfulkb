export type IntakeCase = {
  case_id: string;
  client_id: string;
  status: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

export type IntakeClient = {
  name?: string;
  ico?: string;
  dic?: string;
  legal_form?: string;
  address?: string;
  email?: string | null;
};

// What the Client Intake app's intake-get returns for a link.
export type IntakeData = {
  case_id: string;
  is_mock: boolean;
  case: IntakeCase;
  client: IntakeClient | null;
  can_upload: boolean;
};

// Embedded Chat settings for the Intake Chat agent; null until the Chat SDK key is configured.
export type ChatConfig = {
  sdk_key: string;
  agent_id: string;
  api_url: string;
};

export type ChatPageData = IntakeData & { chat: ChatConfig | null };
