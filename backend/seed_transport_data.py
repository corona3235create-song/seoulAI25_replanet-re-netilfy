
import csv
import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, engine
from backend.models import BusStop, SubwayStation, TtareungiStation

# --- Configuration ---
# Adjust the path to your actual CSV files
BUS_STOPS_CSV_PATH = r"C:\Users\이승재\Downloads\서울AI해커톤\버스정류장 위치정보.csv"
SUBWAY_STATIONS_CSV_PATH = r"C:\Users\이승재\Downloads\서울AI해커톤\지하철역 좌표 데이터.csv"
TTAREUNGI_STATIONS_CSV_PATH = r"C:\Users\이승재\Downloads\서울AI해커톤\따릉이 대여소 위치정보.csv"
# IMPORTANT: Replace DB_NAME_HERE with your actual MySQL database name
DATABASE_URL = "mysql+pymysql://admin:!donggukCAI1234@localhost:3306/seoul-ht-08-db" 

def get_db_session():
    """Creates a new database session."""
    engine = create_engine(DATABASE_URL) # No check_same_thread for MySQL
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def seed_bus_stops(db: Session):
    """Reads bus stop CSV and populates the bus_stops table."""
    if db.query(BusStop).first():
        print("BusStop data already exists. Skipping seeding.")
        return

    print("Seeding bus stops...")
    try:
        with open(BUS_STOPS_CSV_PATH, mode='r', encoding='euc-kr') as csvfile:
            reader = csv.DictReader(csvfile)
            stops_to_add = []
            for row in reader:
                try:
                    stop = BusStop(
                        stop_id=int(row['정류장번호']),
                        stop_name=row['정류장명'],
                        latitude=float(row['위도']),
                        longitude=float(row['경도'])
                    )
                    stops_to_add.append(stop)
                except (ValueError, KeyError) as e:
                    print(f"Skipping row due to error: {row} - {e}")
            
            db.bulk_save_objects(stops_to_add)
            db.commit()
            print(f"Successfully seeded {len(stops_to_add)} bus stops.")

    except FileNotFoundError:
        print(f"ERROR: Bus stops CSV file not found at {BUS_STOPS_CSV_PATH}")
    except Exception as e:
        print(f"An error occurred while seeding bus stops: {e}")


def seed_subway_stations(db: Session):
    """Reads subway station CSV and populates the subway_stations table."""
    if db.query(SubwayStation).first():
        print("SubwayStation data already exists. Skipping seeding.")
        return

    print("Seeding subway stations...")
    try:
        with open(SUBWAY_STATIONS_CSV_PATH, mode='r', encoding='euc-kr') as csvfile:
            # Adjust column names based on the actual (but garbled) CSV structure
            # We infer: "??", "line", "??", "name", "lat", "lon", "??"
            reader = csv.reader(csvfile)
            next(reader) # Skip header row
            
            stations_to_add = []
            for i, row in enumerate(reader):
                try:
                    # Assuming columns are: _, line, _, name, lat, lon, _
                    station = SubwayStation(
                        station_id=i, # Use row number as primary key
                        station_name=row[3], # Inferred station name column
                        line_number=row[1],  # Inferred line number column
                        latitude=float(row[4]),  # Inferred latitude column
                        longitude=float(row[5]) # Inferred longitude column
                    )
                    stations_to_add.append(station)
                except (ValueError, IndexError) as e:
                    print(f"Skipping row due to error: {row} - {e}")

            db.bulk_save_objects(stations_to_add)
            db.commit()
            print(f"Successfully seeded {len(stations_to_add)} subway stations.")

    except FileNotFoundError:
        print(f"ERROR: Subway stations CSV file not found at {SUBWAY_STATIONS_CSV_PATH}")
    except Exception as e:
        print(f"An error occurred while seeding subway stations: {e}")

def seed_ttareungi_stations(db: Session):
    """Reads Ttareungi station CSV and populates the ttareungi_stations table."""
    if db.query(TtareungiStation).first():
        print("TtareungiStation data already exists. Skipping seeding.")
        return

    print("Seeding Ttareungi stations...")
    try:
        with open(TTAREUNGI_STATIONS_CSV_PATH, mode='r', encoding='euc-kr') as csvfile:
            reader = csv.DictReader(csvfile)
            stations_to_add = []
            for row in reader:
                try:
                    station = TtareungiStation(
                        station_id=int(row['대여소']), # Assuming '대여소' is the station ID column
                        station_name=row['대여소명'],
                        latitude=float(row['위도']),
                        longitude=float(row['경도'])
                    )
                    stations_to_add.append(station)
                except (ValueError, KeyError) as e:
                    print(f"Skipping row due to error: {row} - {e}")
            
            db.bulk_save_objects(stations_to_add)
            db.commit()
            print(f"Successfully seeded {len(stations_to_add)} Ttareungi stations.")

    except FileNotFoundError:
        print(f"ERROR: Ttareungi stations CSV file not found at {TTAREUNGI_STATIONS_CSV_PATH}")
    except Exception as e:
        print(f"An error occurred while seeding Ttareungi stations: {e}")


if __name__ == "__main__":
    print("Starting data seeding process...")
    
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(DATABASE_URL)
    print("Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)

    db = get_db_session()
    
    seed_bus_stops(db)
    seed_subway_stations(db)
    seed_ttareungi_stations(db)
    
    db.close()
    print("Data seeding process finished.")

