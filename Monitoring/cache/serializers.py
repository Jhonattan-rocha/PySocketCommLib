"""Cache Serialization Module

Provides different serialization formats for cache data storage.
"""

import json
import pickle
import gzip
import zlib
from abc import ABC, abstractmethod
from typing import Any, Optional, Union
from .config import SerializationFormat


class SerializationError(Exception):
    """Raised when serialization/deserialization fails"""
    pass


class BaseSerializer(ABC):
    """Abstract base class for serializers"""
    
    @abstractmethod
    def serialize(self, data: Any) -> bytes:
        """Serialize data to bytes"""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to data"""
        pass
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """Get the format name"""
        pass


class JSONSerializer(BaseSerializer):
    """JSON serializer with UTF-8 encoding"""
    
    def __init__(self, ensure_ascii: bool = False, indent: Optional[int] = None):
        self.ensure_ascii = ensure_ascii
        self.indent = indent
    
    def serialize(self, data: Any) -> bytes:
        """Serialize data to JSON bytes"""
        try:
            json_str = json.dumps(
                data, 
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
                default=self._json_default
            )
            return json_str.encode('utf-8')
        except (TypeError, ValueError) as e:
            raise SerializationError(f"JSON serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON bytes to data"""
        try:
            json_str = data.decode('utf-8')
            return json.loads(json_str)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise SerializationError(f"JSON deserialization failed: {e}")
    
    def _json_default(self, obj: Any) -> Any:
        """Default JSON serializer for non-standard types"""
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__str__'):
            return str(obj)
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @property
    def format_name(self) -> str:
        return "json"


class PickleSerializer(BaseSerializer):
    """Pickle serializer for Python objects"""
    
    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol
    
    def serialize(self, data: Any) -> bytes:
        """Serialize data to pickle bytes"""
        try:
            return pickle.dumps(data, protocol=self.protocol)
        except (pickle.PicklingError, TypeError) as e:
            raise SerializationError(f"Pickle serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize pickle bytes to data"""
        try:
            return pickle.loads(data)
        except (pickle.UnpicklingError, EOFError, ImportError) as e:
            raise SerializationError(f"Pickle deserialization failed: {e}")
    
    @property
    def format_name(self) -> str:
        return "pickle"


class MsgPackSerializer(BaseSerializer):
    """MessagePack serializer (requires msgpack library)"""
    
    def __init__(self, use_bin_type: bool = True):
        try:
            import msgpack
            self.msgpack = msgpack
        except ImportError:
            raise ImportError("msgpack library is required for MsgPackSerializer")
        
        self.use_bin_type = use_bin_type
    
    def serialize(self, data: Any) -> bytes:
        """Serialize data to MessagePack bytes"""
        try:
            return self.msgpack.packb(
                data, 
                use_bin_type=self.use_bin_type,
                default=self._msgpack_default
            )
        except (TypeError, ValueError) as e:
            raise SerializationError(f"MessagePack serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize MessagePack bytes to data"""
        try:
            return self.msgpack.unpackb(data, raw=False, strict_map_key=False)
        except (ValueError, TypeError) as e:
            raise SerializationError(f"MessagePack deserialization failed: {e}")
    
    def _msgpack_default(self, obj: Any) -> Any:
        """Default MessagePack serializer for non-standard types"""
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        else:
            raise TypeError(f"Object of type {type(obj)} is not MessagePack serializable")
    
    @property
    def format_name(self) -> str:
        return "msgpack"


class CompressedSerializer:
    """Wrapper that adds compression to any serializer"""
    
    def __init__(self, base_serializer: BaseSerializer, 
                 compression_level: int = 6,
                 compression_threshold: int = 1024,
                 use_gzip: bool = False):
        self.base_serializer = base_serializer
        self.compression_level = compression_level
        self.compression_threshold = compression_threshold
        self.use_gzip = use_gzip
        
        # Compression markers
        self.COMPRESSED_MARKER = b'\x1f\x8b'  # gzip magic number
        self.UNCOMPRESSED_MARKER = b'\x00\x00'
    
    def serialize(self, data: Any) -> bytes:
        """Serialize and optionally compress data"""
        # First serialize with base serializer
        serialized = self.base_serializer.serialize(data)
        
        # Compress if data is large enough
        if len(serialized) >= self.compression_threshold:
            if self.use_gzip:
                compressed = gzip.compress(serialized, compresslevel=self.compression_level)
                return self.COMPRESSED_MARKER + compressed[2:]  # Remove gzip header
            else:
                compressed = zlib.compress(serialized, level=self.compression_level)
                return self.COMPRESSED_MARKER + compressed
        else:
            return self.UNCOMPRESSED_MARKER + serialized
    
    def deserialize(self, data: bytes) -> Any:
        """Decompress and deserialize data"""
        if len(data) < 2:
            raise SerializationError("Invalid compressed data: too short")
        
        marker = data[:2]
        payload = data[2:]
        
        if marker == self.COMPRESSED_MARKER:
            # Decompress data
            try:
                if self.use_gzip:
                    # Reconstruct gzip header
                    gzip_data = b'\x1f\x8b' + payload
                    decompressed = gzip.decompress(gzip_data)
                else:
                    decompressed = zlib.decompress(payload)
            except (gzip.BadGzipFile, zlib.error) as e:
                raise SerializationError(f"Decompression failed: {e}")
        elif marker == self.UNCOMPRESSED_MARKER:
            decompressed = payload
        else:
            raise SerializationError(f"Unknown compression marker: {marker.hex()}")
        
        # Deserialize with base serializer
        return self.base_serializer.deserialize(decompressed)
    
    @property
    def format_name(self) -> str:
        compression_type = "gzip" if self.use_gzip else "zlib"
        return f"{self.base_serializer.format_name}+{compression_type}"


class SerializerFactory:
    """Factory for creating serializers"""
    
    _serializers = {
        SerializationFormat.JSON: JSONSerializer,
        SerializationFormat.PICKLE: PickleSerializer,
        SerializationFormat.MSGPACK: MsgPackSerializer
    }
    
    @classmethod
    def create_serializer(cls, format_type: Union[SerializationFormat, str],
                         enable_compression: bool = False,
                         compression_threshold: int = 1024,
                         **kwargs) -> BaseSerializer:
        """Create a serializer instance"""
        if isinstance(format_type, str):
            format_type = SerializationFormat(format_type)
        
        if format_type not in cls._serializers:
            raise ValueError(f"Unsupported serialization format: {format_type}")
        
        # Create base serializer
        serializer_class = cls._serializers[format_type]
        base_serializer = serializer_class(**kwargs)
        
        # Wrap with compression if enabled
        if enable_compression:
            return CompressedSerializer(
                base_serializer,
                compression_threshold=compression_threshold
            )
        
        return base_serializer
    
    @classmethod
    def get_available_formats(cls) -> list:
        """Get list of available serialization formats"""
        return list(cls._serializers.keys())
    
    @classmethod
    def register_serializer(cls, format_type: SerializationFormat, 
                           serializer_class: type):
        """Register a custom serializer"""
        if not issubclass(serializer_class, BaseSerializer):
            raise TypeError("Serializer must inherit from BaseSerializer")
        
        cls._serializers[format_type] = serializer_class


# Utility functions
def estimate_serialized_size(data: Any, format_type: SerializationFormat) -> int:
    """Estimate the serialized size of data without actually serializing"""
    try:
        serializer = SerializerFactory.create_serializer(format_type)
        serialized = serializer.serialize(data)
        return len(serialized)
    except Exception:
        # Fallback estimation based on string representation
        return len(str(data).encode('utf-8'))


def benchmark_serializers(data: Any, iterations: int = 1000) -> dict:
    """Benchmark different serializers with given data"""
    import time
    
    results = {}
    
    for format_type in SerializationFormat:
        try:
            serializer = SerializerFactory.create_serializer(format_type)
            
            # Benchmark serialization
            start_time = time.time()
            for _ in range(iterations):
                serialized = serializer.serialize(data)
            serialize_time = time.time() - start_time
            
            # Benchmark deserialization
            start_time = time.time()
            for _ in range(iterations):
                serializer.deserialize(serialized)
            deserialize_time = time.time() - start_time
            
            results[format_type.value] = {
                'serialize_time': serialize_time,
                'deserialize_time': deserialize_time,
                'total_time': serialize_time + deserialize_time,
                'serialized_size': len(serialized),
                'avg_serialize_time': serialize_time / iterations,
                'avg_deserialize_time': deserialize_time / iterations
            }
            
        except Exception as e:
            results[format_type.value] = {
                'error': str(e)
            }
    
    return results