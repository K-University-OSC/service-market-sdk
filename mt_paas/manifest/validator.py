"""
manifest.yaml 검증기

서비스의 manifest.yaml을 검증합니다.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .schema import Manifest


@dataclass
class ValidationError:
    """검증 오류"""
    path: str
    message: str
    severity: str = "error"  # error, warning


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    manifest: Optional[Manifest] = None
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(self, path: str, message: str):
        self.errors.append(ValidationError(path, message, "error"))
        self.is_valid = False

    def add_warning(self, path: str, message: str):
        self.warnings.append(ValidationError(path, message, "warning"))


class ManifestValidator:
    """
    manifest.yaml 검증기

    Example:
        validator = ManifestValidator()
        result = validator.validate_file("manifest.yaml")
        if result.is_valid:
            manifest = result.manifest
            print(f"Service: {manifest.service.name}")
        else:
            for error in result.errors:
                print(f"Error at {error.path}: {error.message}")
    """

    REQUIRED_FIELDS = {
        "service": ["name", "version"],
        "endpoints": ["base_url"],
    }

    VALID_AUTH_TYPES = ["api_key", "oauth2", "jwt", "none"]
    VALID_CATEGORIES = ["education", "analytics", "communication", "productivity", "other"]

    def __init__(self):
        if not HAS_YAML:
            raise ImportError("PyYAML is required. Install with: pip install pyyaml")

    def validate_file(self, file_path: str) -> ValidationResult:
        """파일 검증"""
        result = ValidationResult(is_valid=True)

        path = Path(file_path)
        if not path.exists():
            result.add_error("file", f"File not found: {file_path}")
            return result

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.add_error("yaml", f"YAML parse error: {e}")
            return result

        return self.validate_dict(data, result)

    def validate_string(self, yaml_string: str) -> ValidationResult:
        """YAML 문자열 검증"""
        result = ValidationResult(is_valid=True)

        try:
            data = yaml.safe_load(yaml_string)
        except yaml.YAMLError as e:
            result.add_error("yaml", f"YAML parse error: {e}")
            return result

        return self.validate_dict(data, result)

    def validate_dict(
        self,
        data: Dict[str, Any],
        result: Optional[ValidationResult] = None
    ) -> ValidationResult:
        """딕셔너리 검증"""
        if result is None:
            result = ValidationResult(is_valid=True)

        if not isinstance(data, dict):
            result.add_error("root", "Manifest must be a dictionary")
            return result

        # 필수 필드 검증
        self._validate_required_fields(data, result)

        if not result.is_valid:
            return result

        # 상세 검증
        self._validate_service(data.get("service", {}), result)
        self._validate_endpoints(data.get("endpoints", {}), result)
        self._validate_auth(data.get("auth", {}), result)
        self._validate_plans(data.get("plans", []), result)
        self._validate_env_vars(data, result)

        # Manifest 객체 생성
        if result.is_valid:
            try:
                result.manifest = Manifest.from_dict(data)
            except Exception as e:
                result.add_error("manifest", f"Failed to create manifest: {e}")

        return result

    def _validate_required_fields(self, data: Dict, result: ValidationResult):
        """필수 필드 검증"""
        for section, fields in self.REQUIRED_FIELDS.items():
            if section not in data:
                result.add_error(section, f"Missing required section: {section}")
                continue

            section_data = data[section]
            if not isinstance(section_data, dict):
                result.add_error(section, f"{section} must be a dictionary")
                continue

            for field in fields:
                if field not in section_data or not section_data[field]:
                    result.add_error(f"{section}.{field}", f"Missing required field: {field}")

    def _validate_service(self, service: Dict, result: ValidationResult):
        """service 섹션 검증"""
        if not service:
            return

        # 버전 형식 검증
        version = service.get("version", "")
        if version and not self._is_valid_version(version):
            result.add_warning("service.version", "Version should be in semver format (e.g., 1.0.0)")

        # 카테고리 검증
        category = service.get("category", "")
        if category and category not in self.VALID_CATEGORIES:
            result.add_warning(
                "service.category",
                f"Unknown category: {category}. Valid values: {self.VALID_CATEGORIES}"
            )

    def _validate_endpoints(self, endpoints: Dict, result: ValidationResult):
        """endpoints 섹션 검증"""
        if not endpoints:
            return

        base_url = endpoints.get("base_url", "")
        if base_url and not (base_url.startswith("http://") or base_url.startswith("https://")):
            result.add_warning("endpoints.base_url", "base_url should start with http:// or https://")

    def _validate_auth(self, auth: Dict, result: ValidationResult):
        """auth 섹션 검증"""
        if not auth:
            return

        auth_type = auth.get("type", "api_key")
        if auth_type not in self.VALID_AUTH_TYPES:
            result.add_error(
                "auth.type",
                f"Invalid auth type: {auth_type}. Valid values: {self.VALID_AUTH_TYPES}"
            )

        if auth_type == "oauth2" and not auth.get("oauth2_config"):
            result.add_error("auth.oauth2_config", "oauth2_config is required when type is oauth2")

    def _validate_plans(self, plans: List, result: ValidationResult):
        """plans 섹션 검증"""
        if not plans:
            result.add_warning("plans", "No plans defined. Consider adding at least one plan.")
            return

        plan_names = set()
        for i, plan in enumerate(plans):
            if not isinstance(plan, dict):
                result.add_error(f"plans[{i}]", "Plan must be a dictionary")
                continue

            name = plan.get("name", "")
            if not name:
                result.add_error(f"plans[{i}].name", "Plan name is required")
            elif name in plan_names:
                result.add_error(f"plans[{i}].name", f"Duplicate plan name: {name}")
            else:
                plan_names.add(name)

    def _validate_env_vars(self, data: Dict, result: ValidationResult):
        """환경변수 검증"""
        required_vars = data.get("required_env_vars", [])
        for var in required_vars:
            if not os.getenv(var):
                result.add_warning(
                    f"env.{var}",
                    f"Required environment variable not set: {var}"
                )

    def _is_valid_version(self, version: str) -> bool:
        """semver 형식 검증"""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))
