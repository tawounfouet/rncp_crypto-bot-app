import logging
import os
from datetime import datetime
from io import BytesIO

import pandas as pd

# Import MinIO client
from minio import Minio
from minio.error import S3Error

# Configurer le logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ClientMinIO")


class ClientMinIO:
    def __init__(self):
        """
        Initialisation du client MinIO avec les variables d'environnement
        """
        # self.endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        self.endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        # self.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        # self.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.access_key = os.environ.get("MINIO_USER_ADMIN", "miniouser")
        self.secret_key = os.environ.get("MINIO_PWD_ADMIN", "miniopassword")
        # self.secure = os.environ.get("MINIO_SECURE", "0").lower
        self.secure = os.environ.get("MINIO_SECURE", "0").lower() in (
            "true",
            "1",
            "yes",
        )
        self.default_bucket = os.environ.get("MINIO_BUCKET", "crypto-bot-data")

        self._client = None

    @property
    def client(self):
        """
        Crée un client MinIO s'il n'existe pas déjà

        Returns:
            Minio: Client MinIO
        """
        if self._client is None:
            try:
                self._client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                )
                logger.info(f"Client MinIO initialisé (endpoint: {self.endpoint})")

                # Vérifier si le bucket par défaut existe
                if not self._client.bucket_exists(self.default_bucket):
                    self._client.make_bucket(self.default_bucket)
                    logger.info(f"Bucket '{self.default_bucket}' créé")
            except Exception as e:
                logger.error(f"Erreur initialisation client MinIO: {e}")
                raise
        return self._client

    def upload_file(self, file_path: str, object_name: str, bucket: str | None = None) -> bool:
        """
        Upload un fichier vers MinIO

        Args:
            file_path (str): Chemin local du fichier
            object_name (str): Nom de l'objet dans MinIO
            bucket (str, optional): Nom du bucket

        Returns:
            bool: True si réussi, False sinon
        """
        bucket_name = bucket or self.default_bucket
        try:
            self.client.fput_object(bucket_name, object_name, file_path)
            logger.info(f"Fichier uploadé avec succès: {bucket_name}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"Erreur upload fichier: {e} (file={file_path}, bucket={bucket_name}, object={object_name})")
            return False

    def upload_dataframe(
        self,
        df: pd.DataFrame,
        object_name: str,
        bucket: str | None = None,
        format: str = "csv",
    ) -> bool:
        """
        Upload un DataFrame pandas vers MinIO

        Args:
            df (pd.DataFrame): DataFrame à uploader
            object_name (str): Nom de l'objet dans MinIO
            bucket (str, optional): Nom du bucket
            format (str): Format de sortie ('csv', 'parquet', 'json')

        Returns:
            bool: True si réussi, False sinon
        """
        bucket_name = bucket or self.default_bucket
        buffer = BytesIO()

        try:
            if format == "csv":
                df.to_csv(buffer)
            elif format == "parquet":
                df.to_parquet(buffer)
            elif format == "json":
                df.to_json(buffer, orient="records")
            else:
                logger.error(f"Format non supporté: {format}")
                return False

            buffer.seek(0)
            size = buffer.getbuffer().nbytes

            self.client.put_object(
                bucket_name,
                object_name,
                buffer,
                size,
                content_type=f"application/{format}" if format != "csv" else "text/csv",
            )
            logger.info(f"DataFrame uploadé avec succès: {bucket_name}/{object_name} (format={format})")
            return True
        except Exception as e:
            logger.error(f"Erreur upload DataFrame: {e} (format={format}, bucket={bucket_name}, object={object_name})")
            return False

    def download_file(self, object_name: str, file_path: str, bucket: str | None = None) -> bool:
        """
        Télécharge un fichier depuis MinIO

        Args:
            object_name (str): Nom de l'objet dans MinIO
            file_path (str): Chemin local où sauvegarder le fichier
            bucket (str, optional): Nom du bucket

        Returns:
            bool: True si réussi, False sinon
        """
        bucket_name = bucket or self.default_bucket
        try:
            self.client.fget_object(bucket_name, object_name, file_path)
            logger.info(f"Fichier téléchargé avec succès: {file_path}")
            return True
        except S3Error as e:
            logger.error(
                f"Erreur téléchargement fichier: {e} (bucket={bucket_name}, object={object_name}, file={file_path})"
            )
            return False

    def download_dataframe(
        self, object_name: str, bucket: str | None = None, format: str = "csv"
    ) -> pd.DataFrame | None:
        """
        Télécharge un fichier depuis MinIO et le charge comme DataFrame

        Args:
            object_name (str): Nom de l'objet dans MinIO
            bucket (str, optional): Nom du bucket
            format (str): Format du fichier ('csv', 'parquet', 'json')

        Returns:
            pd.DataFrame: DataFrame chargé ou None en cas d'erreur
        """
        bucket_name = bucket or self.default_bucket
        buffer = BytesIO()

        try:
            # Téléchargement de l'objet dans un buffer
            response = self.client.get_object(bucket_name, object_name)

            # Lecture des données
            for d in response.stream():
                buffer.write(d)
            buffer.seek(0)
            response.close()
            response.release_conn()

            if format == "csv":
                return pd.read_csv(buffer)
            elif format == "parquet":
                return pd.read_parquet(buffer)
            elif format == "json":
                return pd.read_json(buffer)
            else:
                logger.error(f"Format non supporté: {format}")
                return None
        except Exception as e:
            logger.error(
                f"Erreur téléchargement DataFrame: {e} (format={format}, bucket={bucket_name}, object={object_name})"
            )
            return None

    def list_objects(self, prefix: str = "", bucket: str | None = None) -> list[dict]:
        """
        Liste les objets dans un bucket MinIO

        Args:
            prefix (str): Préfixe pour filtrer les objets
            bucket (str, optional): Nom du bucket

        Returns:
            list: Liste des objets
        """
        bucket_name = bucket or self.default_bucket
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            result = []
            for obj in objects:
                result.append(
                    {
                        "Key": obj.object_name,
                        "Size": obj.size,
                        "LastModified": obj.last_modified,
                    }
                )
            return result
        except S3Error as e:
            logger.error(f"Erreur liste objets: {e} (bucket={bucket_name}, prefix={prefix})")
            return []

    def delete_object(self, object_name: str, bucket: str | None = None) -> bool:
        """
        Supprime un objet de MinIO

        Args:
            object_name (str): Nom de l'objet dans MinIO
            bucket (str, optional): Nom du bucket

        Returns:
            bool: True si réussi, False sinon
        """
        bucket_name = bucket or self.default_bucket
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Objet supprimé avec succès: {bucket_name}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"Erreur suppression objet: {e} (bucket={bucket_name}, object={object_name})")
            return False

    def backup_mongodb_collection(
        self,
        collection_name: str,
        db_name: str = "crypto_market_data",
        bucket: str | None = None,
    ) -> bool:
        """
        Sauvegarde une collection MongoDB dans MinIO

        Args:
            collection_name (str): Nom de la collection
            db_name (str): Nom de la base de données
            bucket (str, optional): Nom du bucket

        Returns:
            bool: True si réussi, False sinon
        """
        import json

        from src.tools.client_mongodb import ClientMongoDB

        mongo_client = None
        try:
            # Connexion à MongoDB
            mongo_client = ClientMongoDB()
            collection = mongo_client.get_collection(collection_name, db_name)

            # Récupérer les données
            data = list(collection.find())

            # Convertir ObjectId en string pour sérialisation JSON
            for doc in data:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

                # Convertir les dates en ISO format
                for k, v in doc.items():
                    if isinstance(v, datetime):
                        doc[k] = v.isoformat()

            # Créer un buffer et y écrire les données JSON
            buffer = BytesIO()
            buffer.write(json.dumps(data, default=str).encode("utf-8"))
            buffer.seek(0)

            # Chemin MinIO
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            object_name = f"backups/mongodb/{db_name}/{collection_name}/{timestamp}.json"
            bucket_name = bucket or self.default_bucket

            # Upload sur MinIO
            size = buffer.getbuffer().nbytes
            self.client.put_object(bucket_name, object_name, buffer, size, content_type="application/json")
            logger.info(f"Collection MongoDB sauvegardée: {bucket_name}/{object_name} ({len(data)} documents)")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde MongoDB: {e} (collection={collection_name}, db={db_name})")
            return False
        finally:
            if mongo_client:
                mongo_client.close()


# Test du client
if __name__ == "__main__":
    import pandas as pd

    # Initialiser le client
    minio_client = ClientMinIO()

    # Créer un DataFrame de test
    df = pd.DataFrame(
        {
            "symbol": ["BTCUSDT", "ETHUSDT", "DOGEUSDT"],
            "price": [40000.0, 2500.0, 0.15],
            "timestamp": [
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ],
        }
    )

    # Upload du DataFrame
    minio_client.upload_dataframe(df, f"test/prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    # Lister les objets
    objects = minio_client.list_objects(prefix="test/")
    for obj in objects:
        print(f"- {obj['Key']} ({obj['Size']} bytes, last modified: {obj['LastModified']})")
