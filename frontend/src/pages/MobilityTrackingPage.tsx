import React, { useState, useEffect } from 'react';
import MobilityTracker from '../components/MobilityTracker';
import PageHeader from '../components/PageHeader';
import { useAuth } from '../contexts/AuthContext'; // Import useAuth to get user info
import { getAuthHeaders } from '../contexts/CreditsContext';
import './MobilityTrackingPage.css';

// Represents a single mobility log entry
interface MobilityLog {
  log_id: number;
  mode: string;
  distance_km: number;
  co2_saved_g: number;
  points_earned: number;
  ended_at: string;
}

// Map transport modes to icons and names
const transportModeDetails: { [key: string]: { icon: string; name: string } } = {
  WALK: { icon: '🚶', name: '도보' },
  BIKE: { icon: '🚲', name: '자전거' },
  TTAREUNGI: { icon: '🚲', name: '따릉이' },
  BUS: { icon: '🚌', name: '버스' },
  SUBWAY: { icon: '🚇', name: '지하철' },
  CAR: { icon: '🚗', name: '자동차' },
  ANY: { icon: '❓', name: '기타' },
};

// New component to display recent mobility logs
const RecentMobilityLogs: React.FC = () => {
  const [logs, setLogs] = useState<MobilityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth(); // Get user from AuthContext

  const fetchLogs = async () => {
    if (!user) return;

    try {
      setLoading(true);
      const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
      // Use the correct, existing endpoint
      const response = await fetch(`${API_URL}/api/credits/mobility/${user.user_id}`, { headers: getAuthHeaders() });
      
      if (!response.ok) {
        throw new Error('Failed to fetch mobility logs.');
      }
      
      const data = await response.json();
      setLogs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    
    // Listen for custom event to refresh logs after a new one is added
    const handleLogAdded = () => fetchLogs();
    window.addEventListener('logAdded', handleLogAdded);
    
    return () => {
      window.removeEventListener('logAdded', handleLogAdded);
    };
  }, [user]); // Re-fetch if user changes

  if (loading) {
    return <div className="loading-spinner"><div></div><div></div><div></div></div>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  return (
    <div className="recent-logs-list">
      {logs.length === 0 ? (
        <div className="no-logs-message">
          <span className="no-logs-icon">🗂️</span>
          <p>최근 이동 기록이 없습니다.</p>
          <span>실시간 이동 기록을 시작해보세요!</span>
        </div>
      ) : (
        logs.map(log => {
          const mode = transportModeDetails[log.mode] || transportModeDetails.ANY;
          return (
            <div key={log.log_id} className="log-item">
              <div className="log-icon">{mode.icon}</div>
              <div className="log-details">
                <span className="log-mode">{mode.name}</span>
                <span className="log-distance">{(log.distance_km).toFixed(2)} km</span>
              </div>
              <div className="log-rewards">
                <span className="log-co2">-{log.co2_saved_g.toFixed(1)}g CO₂</span>
                <span className="log-points">+{log.points_earned} C</span>
              </div>
              <div className="log-time">
                {new Date(log.ended_at).toLocaleDateString()}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};


const MobilityTrackingPage: React.FC = () => {
  return (
    <div className="mobility-tracking-page">
      <PageHeader 
        title="이동 기록 측정"
        subtitle="친환경 이동으로 탄소 발자국을 줄이고 크레딧을 획득하세요."
        icon="🗺️"
      />
      
      <div className="content-grid">
        <div className="card current-activity-card">
          <h3>실시간 활동</h3>
          <MobilityTracker />
        </div>
        
        <div className="card recent-logs-card">
          <h3>최근 기록</h3>
          <RecentMobilityLogs />
        </div>
      </div>
    </div>
  );
};

export default MobilityTrackingPage;