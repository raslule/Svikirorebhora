import { useState, useEffect } from "react";

export default function PredictionHistory() {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await fetch("/api/predict/history", {
        headers: {
          "Authorization": Bearer 
        }
      });
      if (response.ok) {
        const data = await response.json();
        setPredictions(data.predictions);
      }
    } catch (error) {
      console.error("Error fetching prediction history:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCsv = () => {
    const token = localStorage.getItem("token");
    fetch("/api/predict/history/csv", {
      headers: {
        "Authorization": Bearer 
      }
    })
      .then(response => response.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        a.download = "prediction_history.csv";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(error => console.error("Error downloading CSV:", error));
  };

  const isStuckUnresolved = (pred) => {
    if (pred.resolved) return false;
    if (!pred.match_date) return false;
    const matchDate = new Date(pred.match_date);
    const now = new Date();
    const diffDays = (now - matchDate) / (1000 * 60 * 60 * 24);
    return diffDays > 10;
  };

  return (
    <div className="container py-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2>Prediction Ledger</h2>
        <button className="btn btn-outline-primary" onClick={handleDownloadCsv}>
          <i className="bi bi-download me-2"></i> Download CSV
        </button>
      </div>

      {loading ? (
        <div className="text-center">
          <div className="spinner-border" role="status"></div>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead className="table-light">
              <tr>
                <th>Date</th>
                <th>League</th>
                <th>Matchup</th>
                <th className="text-center">Predicted 1X2</th>
                <th className="text-center">Actual Result</th>
                <th className="text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map(pred => {
                const stuck = isStuckUnresolved(pred);
                return (
                  <tr key={pred.id} className={stuck ? "table-warning" : ""}>
                    <td>
                      {pred.match_date 
                        ? new Date(pred.match_date).toLocaleDateString() 
                        : "Unknown"}
                    </td>
                    <td>
                      <span className="badge bg-secondary">{pred.league}</span>
                    </td>
                    <td>
                      <strong>{pred.home_team}</strong> vs <strong>{pred.away_team}</strong>
                    </td>
                    <td className="text-center">
                      <div className="small">
                        H: {(pred.prob_home * 100).toFixed(1)}% | 
                        D: {(pred.prob_draw * 100).toFixed(1)}% | 
                        A: {(pred.prob_away * 100).toFixed(1)}%
                      </div>
                    </td>
                    <td className="text-center">
                      {pred.resolved ? (
                        <span className="fw-bold">
                          {pred.actual_fthg} - {pred.actual_ftag} ({pred.actual_ftr})
                        </span>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td className="text-center">
                      {pred.resolved ? (
                        <span className="badge bg-success">Reconciled</span>
                      ) : stuck ? (
                        <span className="badge bg-danger" title="Match was >10 days ago but no result found">
                          Stuck Unresolved
                        </span>
                      ) : (
                        <span className="badge bg-info text-dark">Pending</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {predictions.length === 0 && (
                <tr>
                  <td colSpan="6" className="text-center py-4 text-muted">
                    No predictions found in ledger.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
