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

export type IntakeData = {
  case_id: string;
  is_mock: boolean;
  case: IntakeCase;
  client: IntakeClient | null;
  can_upload: boolean;
};

export type UploadedDocument = {
  document_id: string;
  filename: string;
  received_at: string;
  content_type: string;
  size_bytes: number;
};
