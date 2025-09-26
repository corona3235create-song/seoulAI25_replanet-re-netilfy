import React from 'react';
import ObjectShop from '../components/ObjectShop';
import { useGarden } from '../hooks/useGarden';
import { useCredits } from '../contexts/CreditsContext';
import { GardenObject } from '../types/garden';
import PageHeader from '../components/PageHeader';
import './ShopPage.css';

function ShopPage() {
  const { purchaseItem, inventory } = useGarden();
  const { creditsData, refreshCredits } = useCredits();

  const handleObjectBuy = async (object: GardenObject) => {
    try {
      await purchaseItem(object);
      await refreshCredits();
    } catch (error) {
      // The error is already logged in the useGarden hook, 
      // but you could add additional user-facing feedback here if needed.
      console.error("Failed to complete purchase on ShopPage:", error);
    }
  };

  return (
    <div className="shop-page">
      <PageHeader 
        title="상점"
        subtitle="크레딧으로 아이템을 구매하여 정원을 꾸며보세요"
        icon="🛒"
      />
      <div className="total-credits-display">
        <span>💰</span>
        <strong>보유 크레딧:</strong> {creditsData.totalCredits.toLocaleString()} C
      </div>
      <div className="shop-grid">
        <ObjectShop onObjectBuy={handleObjectBuy} inventory={inventory} />
      </div>
    </div>
  );
}

export default ShopPage;
