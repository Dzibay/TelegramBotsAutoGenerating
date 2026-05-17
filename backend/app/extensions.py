from passlib.context import CryptContext

bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")
