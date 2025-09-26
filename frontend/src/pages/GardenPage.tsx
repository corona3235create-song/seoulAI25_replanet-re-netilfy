import React, { useState } from 'react';
import { useCredits } from '../contexts/CreditsContext'; // [추가] 중앙 크레딧 시스템 import

// GardenObject 타입 정의 (기존 types/garden.ts 대체)
export interface GardenObject {
  id: number;
  type: string; // 'tree' | 'flower' | 'bench' 등
  x: number;
  y: number;
}

function GardenPage() {
  const { creditsData, addCredits } = useCredits(); // [수정] addCredits 함수를 가져옴
  const [garden, setGarden] = useState<GardenObject[]>([]);

  // 정원 아이템 추가 (기존 GardenEditor 대체)
  const addObject = async (type: string) => { // [수정] async 함수로 변경
    try {
      await addCredits(-10, "정원 아이템 구매"); // [수정] 크레딧 차감 로직 변경
      const newObject: GardenObject = {
        id: Date.now(),
        type,
        x: Math.random() * 300, // 랜덤 위치 예시
        y: Math.random() * 300,
      };
      setGarden((prev) => [...prev, newObject]);
    } catch (error) {
      alert(error instanceof Error ? error.message : "아이템 구매에 실패했습니다.");
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(1, minmax(0, 1fr))', gap: '2rem' }}>
      {/* 크레딧 매니저 (기존 CreditManager 역할) */}
      <div style={{ background: 'white', borderRadius: '1rem', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '1.5rem', border: '1px solid #dcfce7' }}>
        <h2>보유 크레딧: {creditsData.totalCredits}</h2> {/* [변경] 중앙 크레딧 데이터 표시 */}
      </div>

      {/* 정원 에디터 (기존 GardenEditor 역할) */}
      <div style={{ background: 'white', borderRadius: '1rem', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '1.5rem', border: '1px solid #dcfce7' }}>
        <h2>나만의 정원</h2>
        <button onClick={() => addObject("tree")}>🌳 나무 추가</button>
        <button onClick={() => addObject("flower")}>🌸 꽃 추가</button>

        <div style={{ marginTop: "1rem", position: "relative", width: "400px", height: "400px", border: "1px solid #ddd" }}>
          {garden.map((obj) => (
            <div
              key={obj.id}
              style={{
                position: "absolute",
                left: obj.x,
                top: obj.y,
                fontSize: "24px",
              }}
            >
              {obj.type === "tree" ? "🌳" : "🌸"}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default GardenPage;
