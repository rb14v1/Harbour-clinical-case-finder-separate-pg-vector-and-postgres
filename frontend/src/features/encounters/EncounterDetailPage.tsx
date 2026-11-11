import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { extractErrorMessage } from "../../api/client";
import { deleteEncounter, findSimilarEncounters, getEncounter } from "../../api/encounters";
import type { Encounter, SimilarEncounterResult } from "../../types";

export function EncounterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const encounterId = Number(id);
  const navigate = useNavigate();

  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searching, setSearching] = useState(false);
  const [similar, setSimilar] = useState<SimilarEncounterResult[] | null>(null);

  async function loadEncounter() {
    setLoading(true);
    setError(null);
    try {
      const res = await getEncounter(encounterId);
      setEncounter(res.data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEncounter();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encounterId]);

  async function handleFindSimilar() {
    setError(null);
    setSearching(true);
    try {
      const res = await findSimilarEncounters(encounterId);
      setSimilar(res.data.results);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await deleteEncounter(encounterId);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  if (loading) return <p>Loading...</p>;
  if (!encounter) return <p>Encounter not found. <Link to="/">Back to encounters</Link></p>;

  return (
    <div>
      <div className="page-header">
        <h1>{encounter.chief_complaint}</h1>
        <Link to="/">Back to encounters</Link>
      </div>

      {error && <div className="form-error">{error}</div>}

      <div className="card">
        <p><span className="badge badge-specialty">{encounter.specialty.replace("_", " ")}</span></p>
        <p className="muted">Patient: {encounter.patient_name}</p>
        <p className="muted">Clinician: {encounter.clinician_email}</p>
        <p className="muted">Created {new Date(encounter.created_at).toLocaleString()}</p>
        <p className="muted">
          Research consent: {encounter.consent_for_research ? "Yes - eligible to surface to other clinicians" : "No"}
        </p>

        <h3>Notes</h3>
        <p>{encounter.notes}</p>
        <h3>Diagnosis</h3>
        <p>{encounter.diagnosis}</p>
        <h3>Treatment</h3>
        <p>{encounter.treatment}</p>

        <div className="actions" style={{ marginTop: "1rem" }}>
          <button className="danger" onClick={handleDelete}>Delete encounter</button>
        </div>
      </div>

      <div className="card">
        <h2>Find similar past cases</h2>
        <p className="muted">
          Searches consented encounters from this specialty (yours and other clinicians') for clinically
          similar past cases, and shows what they were diagnosed and treated as.
        </p>
        <button onClick={handleFindSimilar} disabled={searching}>
          {searching ? "Searching..." : "Find similar cases"}
        </button>

        {similar !== null && (
          <div className="suggestion-block">
            {similar.length === 0 ? (
              <p className="muted">No similar consented cases found in this specialty yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Chief complaint</th>
                    <th>Diagnosis</th>
                    <th>Treatment</th>
                  </tr>
                </thead>
                <tbody>
                  {similar.map((s) => (
                    <tr key={s.encounter_id}>
                      <td>{s.score.toFixed(3)}</td>
                      <td>{s.chief_complaint}</td>
                      <td>{s.diagnosis}</td>
                      <td>{s.treatment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
