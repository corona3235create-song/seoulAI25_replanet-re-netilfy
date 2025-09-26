  import React, { useState, useEffect } from "react";
  import { useAuth } from "../contexts/AuthContext"; // Import useAuth

  const styles = `
  .challenge-page {
    padding: 2rem;
    text-align: center;
    background-color: #fdfdf5;
    min-height: 100vh;
  }

  .challenge-title {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    color: #2e7d32;
  }

  .challenge-subtitle {
    font-size: 1rem;
    margin-bottom: 2rem;
    color: #555;
  }

  .challenge-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
  }

  .challenge-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s ease;
    text-align: left;
  }

  .challenge-card:hover {
    transform: translateY(-5px);
  }

  .challenge-card h3 {
    margin-bottom: 0.5rem;
    font-size: 1.3rem;
    color: #1b5e20;
  }

  .challenge-card .desc {
    font-size: 0.95rem;
    color: #444;
    margin-bottom: 1rem;
  }

  .progress-bar {
    background: #e0e0e0;
    border-radius: 8px;
    height: 10px;
    margin: 1rem 0;
    overflow: hidden;
  }

  .progress-fill {
    background: linear-gradient(90deg, #42a5f5, #2196f3); /* 파란색 계열로 변경 */
    height: 100%;
    transition: width 0.3s ease;
  }

  .progress-text {
    font-size: 0.9rem;
    color: #444;
  }

  .reward {
    font-weight: bold;
    margin: 0.5rem 0;
    color: #1abc9c;
  }

  .join-btn {
    margin-top: 0.5rem;
    padding: 0.6rem 1rem;
    background: #2e7d32;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s ease;
  }

  .join-btn:hover {
    background: #1b5e20;
  }

  .join-btn:disabled {
    background: #9e9e9e;
    cursor: not-allowed;
  }
  `;

  interface ChallengeData {
    id: number;
    title: string;
    description: string;
    progress: number;
    reward: string;
    is_joined: boolean; // 서버에서 받아올 참여 여부
    is_completed: boolean; // 서버에서 받아올 완료 여부
    status: string; // 챌린지 상태 추가 (예: 'active', 'completed')
  }

  interface AchievementData {
    id: number;
    name: string;
    desc: string;
    date: string | null;
    unlocked: boolean;
    progress: number;
  }

  const Challenge: React.FC = () => {
    const { user } = useAuth(); // Import useAuth
    const [challenges, setChallenges] = useState<ChallengeData[]>([]);
    const [achievements, setAchievements] = useState<AchievementData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // Use user.id if available, otherwise handle the case where user is null
    const currentUserId = user?.id; 
    const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

    // 서버에서 챌린지 목록을 가져오는 함수
    const fetchChallenges = async () => {
      if (!currentUserId) { // Don't fetch if user is not logged in
        setLoading(false);
        setError("로그인이 필요합니다.");
        return;
      }
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/challenges`); // No currentUserId in path
        if (!response.ok) {
          throw new Error('챌린지 정보를 불러오는 데 실패했습니다.');
        }
        const data = await response.json();
        setChallenges(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '알 수 없는 오류 발생');
        setChallenges([]);
      } finally {
        setLoading(false);
      }
    };

    // 컴포넌트가 마운트될 때 챌린지 데이터를 가져옵니다.
    useEffect(() => {
      fetchChallenges();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentUserId]); // Add currentUserId to dependency array

    // 챌린지 참여 처리 함수
    const handleJoinChallenge = async (challengeId: number) => {
      if (!currentUserId) { // Don't join if user is not logged in
        alert("로그인이 필요합니다.");
        return;
      }
      try {
        const response = await fetch(`${API_URL}/api/challenges/${challengeId}/join`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          // user_id is obtained from JWT on the backend, no need to send in body
          body: JSON.stringify({}),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || '챌린지 참여에 실패했습니다.');
        }

        alert('챌린지에 성공적으로 참여했습니다!');
        // 참여 후 목록을 새로고침하여 UI를 업데이트합니다.
        fetchChallenges();

      } catch (error) {
        console.error('챌린지 참여 실패:', error);
        alert(error instanceof Error ? error.message : '챌린지 참여 중 오류가 발생했습니다.');
      }
    };

    // 챌린지 완료 처리 함수
    const handleCompleteChallenge = async (challengeId: number) => {
      if (!currentUserId) {
        alert("로그인이 필요합니다.");
        return;
      }
      try {
        const response = await fetch(`${API_URL}/api/challenges/${challengeId}/complete`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({}), // user_id is obtained from JWT on the backend
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || '챌린지 완료 처리 실패');
        }
        
        alert('챌린지를 성공적으로 완료했습니다! 보상이 지급됩니다.');
        fetchChallenges(); // 완료 후 목록을 새로고침하여 UI를 업데이트합니다。

      } catch (error) {
        console.error('챌린지 완료 처리 오류:', error);
        alert(error instanceof Error ? error.message : '챌린지 완료 처리 중 오류가 발생했습니다.');
      }
    };

    if (loading) return <p>⏳ 로딩 중...</p>;
    if (error) return <p>오류: {error}</p>;
    if (!currentUserId) return <p>로그인하여 챌린지에 참여하세요.</p>; // Display message if not logged in

    return (
      <>
        <style>{styles}</style>
        <div className="challenge-page">
          <h2 className="challenge-title">🔥 나의 챌린지</h2>
          <p className="challenge-subtitle">
            목표를 달성하면 Eco 크레딧과 뱃지를 획득할 수 있어요!
          </p>

          <div className="challenge-grid">
            {challenges.map((c) => (
              <div key={c.id} className="challenge-card">
                <h3>{c.title}</h3>
                <p className="desc">{c.description}</p>

                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${c.progress}%` }}
                  />
                </div>
                <p className="progress-text">{c.progress}% 달성</p>

                <p className="reward">🎁 보상: {c.reward}</p>

                {c.is_joined ? (
                  c.is_completed ? ( // 사용자가 챌린지를 완료한 경우
                    <button className="join-btn" disabled style={{ backgroundColor: '#4CAF50' }}>
                      완료됨
                    </button>
                  ) : ( // 참여 중이지만 아직 완료하지 않은 경우
                    c.progress >= 100 ? ( // 진행률이 100% 이상인 경우
                      <button
                        className="join-btn"
                        onClick={() => handleCompleteChallenge(c.id)}
                      >
                        완료하기
                      </button>
                    ) : ( // 진행 중인 경우
                      <button className="join-btn" disabled>
                        참여중 ({c.progress}%){' '}
                        {/* is_completed가 false이고 progress가 100 미만일 때 */}
                      </button>
                    )
                  )
                ) : ( // 참여하지 않은 챌린지
                  <button 
                    className="join-btn"
                    onClick={() => handleJoinChallenge(c.id)}
                    // 💡 disabled 속성을 제거하여, 참여하지 않은 사용자는 항상 참여 버튼을 볼 수 있게 합니다.
                  >
                    참여하기
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Achievements Section */}
          <h2 className="challenge-title" style={{ marginTop: '3rem' }}>🏆 나의 업적</h2>
          <p className="challenge-subtitle">
            획득한 업적들을 확인해보세요!
          </p>
          <div className="challenge-grid">
            {achievements.length > 0 ? (
              achievements.map((a) => (
                <div key={a.id} className="challenge-card" style={{ borderColor: a.unlocked ? '#4CAF50' : '#ccc' }}>
                  <h3>{a.name}</h3>
                  <p className="desc">{a.desc}</p>
                  {a.unlocked ? (
                    <p style={{ color: '#4CAF50', fontWeight: 'bold' }}>획득일: {a.date}</p>
                  ) : (
                    <p style={{ color: '#9e9e9e' }}>아직 획득하지 못했습니다.</p>
                  )}
                </div>
              ))
            ) : (
              <p>획득한 업적이 없습니다.</p>
            )}
          </div>
        </div>
      </>
    );
  };

  export default Challenge;