"""Read-only MongoDB access for jasentool; nothing here writes to a database."""
import re
import sys

import pymongo

from jasentool.log import get_logger

logger = get_logger(__name__)

class Database:
    """Class that assists in handling mongodb request"""
    uri = "mongodb://localhost:27017/"
    db = None
    db_name = None

    @classmethod
    def initialize(cls, db_name, uri=None):
        """Initialize mongodb client. Pass `uri` to override the default."""
        if uri is not None:
            cls.uri = uri
        client = pymongo.MongoClient(cls.uri)
        cls.db = client[db_name]
        cls.db_name = db_name

    @classmethod
    def location(cls, collection):
        """`<db>.<collection> at <uri>`, with any password in the URI hidden."""
        return f"{cls.db_name}.{collection} at {re.sub(r'//[^/@]*@', '//***@', cls.uri)}"

    @classmethod
    def require_collection(cls, collection):
        """Exit with an error unless the collection exists in the database."""
        try:
            found = collection in cls.db.list_collection_names()
        except pymongo.errors.PyMongoError as exc:
            logger.error("Could not read %s: %s", cls.location(collection), exc)
            sys.exit(1)
        if not found:
            logger.error("No collection %s; check the address, database and collection names",
                         cls.location(collection))
            sys.exit(1)

    @staticmethod
    def find(collection, query, fields):
        """Find data in mongodb"""
        return list(Database.db[collection].find(query, fields))

    @staticmethod
    def find_one(collection, query):
        """Find one entry in mongodb"""
        return Database.db[collection].find_one(query)

    @staticmethod
    def get_pvl(collection, query):
        """Get pvl result data from mongodb"""
        return Database.db[collection].find(query, {"_id": 0, "aribavir.lukS_PV.present": 1})

    @staticmethod
    def get_mlst(collection, query):
        """Get mlst result data from mongodb"""
        return Database.db[collection].find(query, {"_id": 0, "mlst": 1})

    @staticmethod
    def get_cgmlst(collection, query):
        """Get cgmlst result data from mongodb"""
        return Database.db[collection].find(query, {"_id": 0, "alleles": 1})

    @staticmethod
    def get_meta_fields():
        """Get respective metadata from mongodb"""
        fields = {
            "id": 1,
            "mlst.sequence_type": 1,
            "aribavir.lukF_PV.present": 1,
            "aribavir.lukS_PV.present": 1,
            "missing": 1,
            "metadata.QC": 1,
            "metadata.Comment": 1,
            "run": 1
        }
        return fields
