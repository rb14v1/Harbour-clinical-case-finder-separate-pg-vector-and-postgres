import { useEffect, useState } from "react";

import { extractErrorMessage } from "../../api/client";
import { createPatient, listPatients } from "../../api/patients";
import type { Patient } from "../../types";

export function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [mrn, setMrn] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadPatients() {
    setLoading(true);
    setError(null);
    try {
      const res = await listPatients();
      setPatients(res.data.results);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPatients();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName.trim() || !dateOfBirth || !mrn.trim()) {
      setError("Full name, date of birth, and MRN are required.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await createPatient({ full_name: fullName, date_of_birth: dateOfBirth, mrn });
      setFullName("");
      setDateOfBirth("");
      setMrn("");
      await loadPatients();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Patients</h1>
      </div>

      <div className="card">
        <form className="inline-form" onSubmit={handleSubmit}>
          <label style={{ flex: 1, minWidth: 200 }}>
            Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label>
            Date of birth
            <input type="date" value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)} required />
          </label>
          <label>
            MRN
            <input value={mrn} onChange={(e) => setMrn(e.target.value)} required />
          </label>
          <button type="submit" disabled={submitting}>{submitting ? "Adding..." : "Add patient"}</button>
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
                <th>Full name</th>
                <th>Date of birth</th>
                <th>MRN</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((p) => (
                <tr key={p.id}>
                  <td>{p.full_name}</td>
                  <td>{p.date_of_birth}</td>
                  <td>{p.mrn}</td>
                </tr>
              ))}
              {patients.length === 0 && (
                <tr><td colSpan={3} className="muted">No patients yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
