from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str
    pk: bool = False
    nullable: bool = True
    comment: str = ""


class ForeignKey(BaseModel):
    column: str
    references: str


class Index(BaseModel):
    name: str
    columns: list[str]
    unique: bool = False


class Table(BaseModel):
    name: str
    comment: str = ""
    columns: list[Column] = Field(default_factory=list)
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    tables: list[Table] = Field(default_factory=list)


class Param(BaseModel):
    name: str
    type: str
    annotation: str   # "RequestParam" | "RequestBody" | "PathVariable"
    required: bool = True


class JavaField(BaseModel):
    """Java 클래스의 필드 정보 (Entity/DTO 멤버 변수)"""
    name: str
    type: str
    comment: str = ""


class Endpoint(BaseModel):
    method: str
    path: str
    controller: str
    service: str
    calls: list[str] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    returnType: str = ""
    requestFields: list[JavaField] = Field(default_factory=list)
    responseFields: list[JavaField] = Field(default_factory=list)


class ApiSchema(BaseModel):
    endpoints: list[Endpoint] = Field(default_factory=list)
    classFields: dict[str, list[JavaField]] = Field(default_factory=dict)


class Module(BaseModel):
    name: str
    type: str
    file: str
    dependsOn: list[str] = Field(default_factory=list)
    layer: str


class ExternalCall(BaseModel):
    source: str = Field(alias="from", serialization_alias="from")
    type: str
    command: str
    file: str
    line: int

    model_config = {"populate_by_name": True}


class DependencySchema(BaseModel):
    modules: list[Module] = Field(default_factory=list)
    externalCalls: list[ExternalCall] = Field(default_factory=list)


class Component(BaseModel):
    name: str
    file: str
    children: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)


class ApiCall(BaseModel):
    component: str
    method: str
    path: str
    file: str
    line: int


class FrontendSchema(BaseModel):
    components: list[Component] = Field(default_factory=list)
    apiCalls: list[ApiCall] = Field(default_factory=list)


class ScanResult(BaseModel):
    version: str = "1.0"
    project: str
    scannedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    database: DatabaseSchema = Field(default_factory=DatabaseSchema)
    api: ApiSchema = Field(default_factory=ApiSchema)
    dependencies: DependencySchema = Field(default_factory=DependencySchema)
    frontend: FrontendSchema = Field(default_factory=FrontendSchema)
