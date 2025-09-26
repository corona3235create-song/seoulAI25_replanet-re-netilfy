
import os
import json
from sqlalchemy.orm import Session
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import func

from backend import schemas, models, crud
from backend.services.group_challenge_service import GroupChallengeService

# Constants from mobility.py
DEFAULT_CARBON_FACTORS = {
    schemas.TransportMode.WALK.value: 0,
    schemas.TransportMode.BIKE.value: 0,
    schemas.TransportMode.TTAREUNGI.value: 0,
    schemas.TransportMode.BUS.value: 100,
    schemas.TransportMode.SUBWAY.value: 50,
    schemas.TransportMode.CAR.value: 170,
}
CARBON_EMISSION_FACTORS_G_PER_KM = json.loads(
    os.getenv("CARBON_EMISSION_FACTORS_JSON", json.dumps(DEFAULT_CARBON_FACTORS))
)
CREDIT_PER_G_CO2 = float(os.getenv("CREDIT_PER_G_CO2", 0.1))

class MobilityService:
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Radius of Earth in kilometers
        dLat = radians(lat2 - lat1)
        dLon = radians(lon2 - lon1)
        a = sin(dLat / 2) * sin(dLat / 2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2) * sin(dLon / 2)
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c
        return distance

    @staticmethod
    def detect_transport_mode(db: Session, latitude: float, longitude: float, speed_kmh: float) -> schemas.TransportMode | None:
        """
        Detects the transport mode based on the user's location and speed.
        """
        # Find the nearest bus stop
        nearest_bus_stop = db.query(models.BusStop).order_by(
            func.pow(models.BusStop.latitude - latitude, 2) + func.pow(models.BusStop.longitude - longitude, 2)
        ).first()

        # Find the nearest subway station
        nearest_subway_station = db.query(models.SubwayStation).order_by(
            func.pow(models.SubwayStation.latitude - latitude, 2) + func.pow(models.SubwayStation.longitude - longitude, 2)
        ).first()

        # Find the nearest Ttareungi station
        nearest_ttareungi_station = db.query(models.TtareungiStation).order_by(
            func.pow(models.TtareungiStation.latitude - latitude, 2) + func.pow(models.TtareungiStation.longitude - longitude, 2)
        ).first()

        bus_stop_distance = float('inf')
        if nearest_bus_stop:
            bus_stop_distance = MobilityService.haversine(latitude, longitude, nearest_bus_stop.latitude, nearest_bus_stop.longitude)

        subway_station_distance = float('inf')
        if nearest_subway_station:
            subway_station_distance = MobilityService.haversine(latitude, longitude, nearest_subway_station.latitude, nearest_subway_station.longitude)

        ttareungi_station_distance = float('inf')
        if nearest_ttareungi_station:
            ttareungi_station_distance = MobilityService.haversine(latitude, longitude, nearest_ttareungi_station.latitude, nearest_ttareungi_station.longitude)

        if bus_stop_distance < 0.2:  # 200 meters threshold
            return schemas.TransportMode.BUS
        elif subway_station_distance < 0.2:  # 200 meters threshold
            return schemas.TransportMode.SUBWAY
        elif speed_kmh < 10:
            return schemas.TransportMode.WALK
        elif 10 <= speed_kmh <= 25:
            if ttareungi_station_distance < 0.2: # 200 meters threshold
                return schemas.TransportMode.TTAREUNGI
            else:
                return schemas.TransportMode.BIKE
        else:
            return None

    @staticmethod
    def log_mobility(db: Session, log_data: schemas.MobilityLogCreate, user: models.User) -> models.MobilityLog:
        """
        Logs mobility data, creates a credit ledger entry, and updates challenge progress.
        """
        # 1. Detect transport mode if not provided
        if not log_data.mode:
            if log_data.start_point and log_data.started_at and log_data.ended_at:
                lat, lon = map(float, log_data.start_point.split(','))
                duration_hours = (log_data.ended_at - log_data.started_at).total_seconds() / 3600
                speed_kmh = log_data.distance_km / duration_hours if duration_hours > 0 else 0
                log_data.mode = MobilityService.detect_transport_mode(db, lat, lon, speed_kmh)

        if not log_data.mode:
            log_data.mode = schemas.TransportMode.WALK # Fallback to WALK if no mode is detected

        # 2. Calculate CO2 saved and points earned
        if log_data.distance_km == 0:
            co2_saved_g = 0
            points_earned = 0
            mode_emission = 0
            car_emission_baseline = 0
        else:
            mode_emission = CARBON_EMISSION_FACTORS_G_PER_KM.get(log_data.mode.value, 0)
            car_emission_baseline = CARBON_EMISSION_FACTORS_G_PER_KM.get(schemas.TransportMode.CAR.value, 170)

            co2_saved_g = 0
            if log_data.mode in [schemas.TransportMode.WALK, schemas.TransportMode.BIKE, schemas.TransportMode.BUS, schemas.TransportMode.SUBWAY, schemas.TransportMode.TTAREUNGI]:
                co2_saved_g = (car_emission_baseline - mode_emission) * log_data.distance_km
                if co2_saved_g < 0:
                    co2_saved_g = 0
            
            points_earned = int(co2_saved_g * CREDIT_PER_G_CO2)

        # 3. Create MobilityLog entry
        db_mobility_log = models.MobilityLog(
            user_id=user.user_id,
            mode=log_data.mode,
            distance_km=log_data.distance_km,
            started_at=log_data.started_at,
            ended_at=log_data.ended_at,
            co2_baseline_g=car_emission_baseline * log_data.distance_km,
            co2_actual_g=mode_emission * log_data.distance_km,
            co2_saved_g=co2_saved_g,
            points_earned=points_earned,
            description=log_data.description,
            start_point=log_data.start_point,
            end_point=log_data.end_point,
            created_at=datetime.utcnow(),
        )
        db.add(db_mobility_log)
        db.flush() # Flush to get the log_id for the credit entry reference

        # 4. Create CreditsLedger entry
        if points_earned > 0:
            db_credit_entry = models.CreditsLedger(
                user_id=user.user_id,
                ref_log_id=db_mobility_log.log_id,
                type=schemas.CreditType.EARN,
                points=points_earned,
                reason=f"Mobility: {log_data.mode.value} for {log_data.distance_km:.2f} km",
                created_at=datetime.utcnow()
            )
            db.add(db_credit_entry)

        # 5. Update challenge progress
        if co2_saved_g > 0 or log_data.distance_km > 0:
            # Update group challenges
            GroupChallengeService.update_challenge_progress(db, user_id=user.user_id, co2_saved=float(co2_saved_g))
            
            # Update personal challenges
            user_challenges = db.query(models.ChallengeMember).filter(
                models.ChallengeMember.user_id == user.user_id,
                models.ChallengeMember.is_completed == False
            ).all()

            for member_entry in user_challenges:
                challenge = db.query(models.Challenge).filter(models.Challenge.challenge_id == member_entry.challenge_id).first()
                
                if not challenge or not (challenge.start_at <= datetime.utcnow() <= challenge.end_at):
                    continue

                # Check if the mobility mode matches the challenge target mode
                if challenge.target_mode != models.TransportMode.ANY and challenge.target_mode != log_data.mode:
                    continue

                progress_to_add = 0
                if challenge.goal_type == models.ChallengeGoalType.CO2_SAVED:
                    progress_to_add = co2_saved_g
                elif challenge.goal_type == models.ChallengeGoalType.DISTANCE_KM:
                    progress_to_add = log_data.distance_km
                elif challenge.goal_type == models.ChallengeGoalType.TRIP_COUNT:
                    progress_to_add = 1

                if progress_to_add > 0:
                    crud.update_personal_challenge_progress(
                        db,
                        user_id=user.user_id,
                        challenge_id=challenge.challenge_id,
                        progress_increment=progress_to_add
                    )

        db.commit()
        db.refresh(db_mobility_log)

        return db_mobility_log
