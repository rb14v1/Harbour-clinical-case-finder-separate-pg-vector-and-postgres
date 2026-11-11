import { apiClient } from "./client";
import type { Encounter, Paginated, SimilarEncountersResponse, Specialty } from "../types";

export interface EncounterFilters {
  specialty?: Specialty | "";
}

export interface EncounterInput {
  patient: number;
  specialty: Specialty;
  chief_complaint: string;
  notes: string;
  diagnosis: string;
  treatment: string;
  consent_for_research: boolean;
}

export function listEncounters(filters: EncounterFilters = {}) {
  return apiClient.get<Paginated<Encounter>>("/encounters/", {
    params: { specialty: filters.specialty || undefined },
  });
}

export function getEncounter(id: number) {
  return apiClient.get<Encounter>(`/encounters/${id}/`);
}

export function createEncounter(data: EncounterInput) {
  return apiClient.post<Encounter>("/encounters/", data);
}

export function updateEncounter(id: number, data: Partial<EncounterInput>) {
  return apiClient.patch<Encounter>(`/encounters/${id}/`, data);
}

export function deleteEncounter(id: number) {
  return apiClient.delete(`/encounters/${id}/`);
}

export function findSimilarEncounters(id: number, topK = 5) {
  return apiClient.get<SimilarEncountersResponse>(`/encounters/${id}/similar/`, {
    params: { top_k: topK },
  });
}
