import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { extractErrorMessage } from "../../api/client";
import { createEncounter, listEncounters } from "../../api/encounters";
import { listPatients } from "../../api/patients";
import type { Encounter, Patient, Specialty } from "../../types";

const SPECIALTIES: Specialty[] = ["cardiology", "pediatrics", "oncology", "general_medicine", "dermatology"];

export function EncountersPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [specialtyFilter, setSpecialtyFilter] = useState<Specialty | "">("");

  const [patientId, setPatientId] = useState<string>("");
  const [specialty, setSpecialty] = useState<Specialty>("cardiology");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [notes, setNotes] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [treatment, setTreatment] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [encRes, patRes] = await Promise.all([
        listEncounters({ specialty: specialtyFilter || undefined }),
        listPatients(),
      ]);
      setEncounters(encRes.data.results);
      setPatients(patRes.data.results);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specialtyFilter]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!patientId || !chiefComplaint.trim() || !notes.trim() || !diagnosis.trim() || !treatment.trim()) {
      setError("All fields are required.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await createEncounter({
        patient: Number(patientId),
        specialty,
        chief_complaint: chiefComplaint,
        notes,
        diagnosis,
        treatment,
        consent_for_research: consent,
      });
      setChiefComplaint("");
      setNotes("");
      setDiagnosis("");
      setTreatment("");
      setConsent(false);
      await loadData();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Encounters</h1>
      </div>

      <div className="card">
        <div className="form-row">
          <label>
            Specialty
            <select value={specialtyFilter} onChange={(e) => setSpecialtyFilter(e.target.value as Specialty | "")}>
              <option value="">All</option>
              {SPECIALTIES.map((s) => (
                <option key={s} value={s}>{s.replace("_", " ")}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="card">
        <h2>Log a new encounter</h2>
        <form className="encounter-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <label>
              Patient
              <select value={patientId} onChange={(e) => setPatientId(e.target.value)} required>
                <option value="">Select patient</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name} (MRN {p.mrn})</option>
                ))}
              </select>
            </label>
            <label>
              Specialty
              <select value={specialty} onChange={(e) => setSpecialty(e.target.value as Specialty)}>
                {SPECIALTIES.map((s) => (
                  <option key={s} value={s}>{s.replace("_", " ")}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Chief complaint
            <input value={chiefComplaint} onChange={(e) => setChiefComplaint(e.target.value)} required />
          </label>
          <label>
            Notes
            <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} required />
          </label>
          <label>
            Diagnosis
            <input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} required />
          </label>
          <label>
            Treatment
            <input value={treatment} onChange={(e) => setTreatment(e.target.value)} required />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            Patient consented to this encounter being used for research (similarity search by other clinicians)
          </label>
          <button type="submit" disabled={submitting}>{submitting ? "Saving..." : "Save encounter"}</button>
        </form>
        {error && <div className="form-error">{error}</div>}
      </div>

      <div className="card">
        {loading ? (
          <p>Loading...</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th>Specialty</th>
                <th>Chief complaint</th>
                <th>Consent</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {encounters.map((e) => (
                <tr key={e.id}>
                  <td>{e.patient_name}</td>
                  <td><span className="badge badge-specialty">{e.specialty.replace("_", " ")}</span></td>
                  <td>{e.chief_complaint}</td>
                  <td>{e.consent_for_research ? "Yes" : "No"}</td>
                  <td>{new Date(e.created_at).toLocaleString()}</td>
                  <td className="actions">
                    <Link to={`/encounters/${e.id}`}>View</Link>
                  </td>
                </tr>
              ))}
              {encounters.length === 0 && (
                <tr><td colSpan={6} className="muted">No encounters for this filter.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
