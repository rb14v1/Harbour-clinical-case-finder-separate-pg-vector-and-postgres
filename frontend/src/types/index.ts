export type Role = "clinician" | "admin";

export type Specialty =
  | "cardiology"
  | "pediatrics"
  | "oncology"
  | "general_medicine"
  | "dermatology";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  specialty: string | null;
  date_joined: string;
}

export interface Patient {
  id: number;
  full_name: string;
  date_of_birth: string;
  mrn: string;
  created_at: string;
}

export interface Encounter {
  id: number;
  patient: number;
  patient_name: string;
  clinician: number;
  clinician_email: string;
  specialty: Specialty;
  chief_complaint: string;
  notes: string;
  diagnosis: string;
  treatment: string;
  consent_for_research: boolean;
  created_at: string;
}

export interface SimilarEncounterResult {
  encounter_id: number;
  score: number;
  specialty: Specialty;
  chief_complaint: string;
  diagnosis: string;
  treatment: string;
  clinician_id: number;
}

export interface SimilarEncountersResponse {
  results: SimilarEncounterResult[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
