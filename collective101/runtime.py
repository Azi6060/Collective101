"""Compatibility imports for earlier event-planning callers.

DepartmentOrganization is the canonical organization engine. Historical CLI
commands and recorded event-plan state retain this frozen implementation.
"""
from .legacy.runtime import Organization, ReviewRejected
from .department_runtime import DepartmentOrganization

__all__ = ['Organization', 'ReviewRejected', 'DepartmentOrganization']
