import { apiClient } from "./client";
import type { Paginated, Patient } from "../types";

export interface PatientInput {
  full_name: string;
  date_of_birth: string;
  mrn: string;
}

export function listPatients() {
  return apiClient.get<Paginated<Patient>>("/patients/");
}

export function createPatient(data: PatientInput) {
  return apiClient.post<Patient>("/patients/", data);
}
