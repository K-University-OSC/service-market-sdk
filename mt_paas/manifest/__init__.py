"""
manifest.yaml 검증 및 파싱 모듈

서비스의 manifest.yaml을 검증하고 파싱합니다.

사용 예시:
    from mt_paas.manifest import ManifestValidator, Manifest

    # 검증
    validator = ManifestValidator()
    result = validator.validate_file("manifest.yaml")
    if result.is_valid:
        manifest = result.manifest
        print(f"Service: {manifest.service.name}")
"""

from .validator import ManifestValidator, ValidationResult
from .schema import (
    Manifest,
    ServiceInfo,
    Endpoints,
    AuthConfig,
    PlanConfig,
    UsageMetric,
)

__all__ = [
    "ManifestValidator",
    "ValidationResult",
    "Manifest",
    "ServiceInfo",
    "Endpoints",
    "AuthConfig",
    "PlanConfig",
    "UsageMetric",
]
