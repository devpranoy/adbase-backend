"""OpenAPI document for the Adbase backend."""

from typing import Any


def build_openapi_spec(server_url: str | None = None) -> dict[str, Any]:
    servers = []
    if server_url:
        servers.append({"url": server_url.rstrip("/")})

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Adbase Backend API",
            "version": "1.0.0",
            "description": (
                "API for authentication, reusable synthetic actors, UGC ad generation, "
                "audio generation, and full pipeline orchestration."
            ),
        },
        "servers": servers,
        "tags": [
            {"name": "Auth"},
            {"name": "Actors"},
            {"name": "Jobs"},
            {"name": "Agents"},
            {"name": "Voices"},
            {"name": "Utility"},
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["error"],
                },
                "AuthCredentials": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                    "required": ["username", "password"],
                },
                "TokenResponse": {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string"},
                    },
                    "required": ["token"],
                },
                "VoiceOption": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "voice_id": {"type": "string"},
                        "sample_url": {"type": "string", "format": "uri"},
                    },
                    "required": ["name", "voice_id", "sample_url"],
                },
                "ActorVariant": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "actor_id": {"type": "string", "format": "uuid"},
                        "user_id": {"type": "string", "format": "uuid"},
                        "status": {
                            "type": "string",
                            "enum": ["generating", "ready", "failed"],
                        },
                        "image_url": {"type": "string", "nullable": True},
                        "thumbnail_url": {"type": "string", "nullable": True},
                        "prompt": {"type": "string"},
                        "replicate_model": {"type": "string", "nullable": True},
                        "replicate_prediction_id": {"type": "string", "nullable": True},
                        "seed": {"type": "string", "nullable": True},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "is_primary": {"type": "boolean"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"},
                    },
                },
                "Actor": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "user_id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string", "nullable": True},
                        "status": {
                            "type": "string",
                            "enum": ["draft", "generating", "ready", "failed", "archived"],
                        },
                        "age_band": {
                            "type": "string",
                            "enum": ["18-24", "25-34", "35-44", "45-54", "55+"],
                        },
                        "ethnicity": {"type": "string"},
                        "gender_presentation": {"type": "string", "nullable": True},
                        "prompt": {"type": "string"},
                        "attributes": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "primary_variant": {
                            "allOf": [{"$ref": "#/components/schemas/ActorVariant"}],
                            "nullable": True,
                        },
                        "variant_count": {"type": "integer"},
                        "variants": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ActorVariant"},
                        },
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"},
                    },
                },
                "Job": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "status": {
                            "type": "string",
                            "enum": ["draft", "processing", "succeeded", "failed"],
                        },
                        "image_url": {"type": "string", "nullable": True},
                        "prompt": {"type": "string", "nullable": True},
                        "actor_variant_id": {"type": "string", "format": "uuid", "nullable": True},
                        "replicate_prediction_id": {"type": "string", "nullable": True},
                        "output_video_url": {"type": "string", "nullable": True},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                },
                "AgentOutputs": {
                    "type": "object",
                    "properties": {
                        "script_writer": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "story_writer": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "meta": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                },
            },
        },
        "paths": {
            "/api/auth/login": {
                "post": {
                    "tags": ["Auth"],
                    "summary": "Log in with username and password",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AuthCredentials"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "JWT issued",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TokenResponse"}
                                }
                            },
                        },
                        "401": {
                            "description": "Invalid credentials",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/auth/register": {
                "post": {
                    "tags": ["Auth"],
                    "summary": "Create a user and issue a JWT",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AuthCredentials"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "User created and JWT issued",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TokenResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Missing username or password",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                        "409": {
                            "description": "Username already exists",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/actors": {
                "get": {
                    "tags": ["Actors"],
                    "summary": "List actors",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "in": "query",
                            "name": "limit",
                            "schema": {"type": "integer", "default": 50, "maximum": 100},
                        },
                        {
                            "in": "query",
                            "name": "offset",
                            "schema": {"type": "integer", "default": 0, "minimum": 0},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Actor list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "actors": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Actor"},
                                            },
                                            "total": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/actors/generate": {
                "post": {
                    "tags": ["Actors"],
                    "summary": "Create a synthetic actor and generate portrait variants",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "age_band": {
                                            "type": "string",
                                            "enum": ["18-24", "25-34", "35-44", "45-54", "55+"],
                                        },
                                        "ethnicity": {"type": "string"},
                                        "gender_presentation": {"type": "string"},
                                        "traits": {
                                            "oneOf": [
                                                {"type": "string"},
                                                {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                {
                                                    "type": "object",
                                                    "additionalProperties": True,
                                                },
                                            ]
                                        },
                                        "prompt_override": {"type": "string"},
                                        "model": {"type": "string"},
                                        "image_count": {"type": "integer", "minimum": 1},
                                    },
                                    "required": ["age_band", "ethnicity"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Actor created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "actor": {"$ref": "#/components/schemas/Actor"},
                                            "generation_model": {"type": "string"},
                                            "warnings": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/actors/{actor_id}": {
                "get": {
                    "tags": ["Actors"],
                    "summary": "Get actor details and variants",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "actor_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Actor details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "actor": {"$ref": "#/components/schemas/Actor"}
                                        },
                                    }
                                }
                            },
                        },
                        "404": {
                            "description": "Actor not found",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/actors/{actor_id}/variants": {
                "post": {
                    "tags": ["Actors"],
                    "summary": "Generate more variants for an existing actor",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "actor_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "variation_prompt": {"type": "string"},
                                        "prompt_override": {"type": "string"},
                                        "model": {"type": "string"},
                                        "image_count": {"type": "integer", "minimum": 1},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Variants created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "actor": {"$ref": "#/components/schemas/Actor"},
                                            "created_variants": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/ActorVariant"},
                                            },
                                            "generation_model": {"type": "string"},
                                            "warnings": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/actors/{actor_id}/select-primary": {
                "post": {
                    "tags": ["Actors"],
                    "summary": "Mark one variant as the actor's primary portrait",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "actor_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "actor_variant_id": {"type": "string", "format": "uuid"}
                                    },
                                    "required": ["actor_variant_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Primary variant updated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "actor": {"$ref": "#/components/schemas/Actor"}
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/voices/elevenlabs-v3": {
                "get": {
                    "tags": ["Voices"],
                    "summary": "List supported TTS voices",
                    "security": [{"bearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Voice options",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "voices": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/VoiceOption"},
                                            },
                                            "default_voice": {"$ref": "#/components/schemas/VoiceOption"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "List jobs",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "in": "query",
                            "name": "limit",
                            "schema": {"type": "integer", "default": 50, "maximum": 100},
                        },
                        {
                            "in": "query",
                            "name": "offset",
                            "schema": {"type": "integer", "default": 0, "minimum": 0},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Job list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "jobs": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Job"},
                                            },
                                            "total": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/upload": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Upload a single product image and create a draft job",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "image": {"type": "string", "format": "binary"},
                                        "prompt": {"type": "string"},
                                    },
                                    "required": ["image"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Draft job created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "image_url": {"type": "string"},
                                            "prompt": {"type": "string"},
                                            "status": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/upload-full": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Upload product assets and optional actor input for the full pipeline",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "product_images": {
                                            "type": "array",
                                            "items": {"type": "string", "format": "binary"},
                                        },
                                        "image": {"type": "string", "format": "binary"},
                                        "actor_image": {"type": "string", "format": "binary"},
                                        "actor_variant_id": {"type": "string", "format": "uuid"},
                                        "prompt": {"type": "string"},
                                        "voice": {"type": "string"},
                                        "product_info": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Draft full-pipeline job created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "status": {"type": "string"},
                                            "prompt": {"type": "string"},
                                            "voice": {"type": "string", "nullable": True},
                                            "product_info": {"nullable": True},
                                            "actor_variant_id": {"type": "string", "format": "uuid", "nullable": True},
                                            "actor_image_url": {"type": "string", "nullable": True},
                                            "product_image_urls": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "manifest_url": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "Get job status",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Job status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [{"$ref": "#/components/schemas/Job"}],
                                        "type": "object",
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}/result": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "Get the final job result URL when ready",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Job result is ready",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "output_video_url": {"type": "string"}
                                        },
                                    }
                                }
                            },
                        },
                        "202": {
                            "description": "Job still processing",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                    },
                }
            },
            "/api/jobs/{job_id}/pipeline": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "Get the stored full-pipeline manifest",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Pipeline manifest",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "pipeline": {
                                                "type": "object",
                                                "additionalProperties": True,
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}/start": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Start a single image-to-video job",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "use_agents": {"type": "boolean"},
                                        "prompt_override": {"type": "string"},
                                        "tone": {"type": "string"},
                                        "duration_target_sec": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Job started",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "prediction_id": {"type": "string"},
                                            "status": {"type": "string"},
                                            "used_prompt": {"type": "string"},
                                            "agent_outputs": {
                                                "$ref": "#/components/schemas/AgentOutputs"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}/agents": {
                "post": {
                    "tags": ["Agents"],
                    "summary": "Generate script and story outputs for an existing job",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt_override": {"type": "string"},
                                        "tone": {"type": "string"},
                                        "duration_target_sec": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Agent outputs",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "agent_outputs": {
                                                "$ref": "#/components/schemas/AgentOutputs"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/agents/generate": {
                "post": {
                    "tags": ["Agents"],
                    "summary": "Generate ad script and story outputs from a freeform prompt",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "image_url": {"type": "string"},
                                        "tone": {"type": "string"},
                                        "duration_target_sec": {"type": "integer"},
                                    },
                                    "required": ["prompt"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Agent outputs",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/AgentOutputs"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}/audio": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Generate TTS audio for a job",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "voice": {"type": "string"},
                                        "language_code": {"type": "string"},
                                        "speed": {"type": "number"},
                                        "stability": {"type": "number"},
                                        "similarity_boost": {"type": "number"},
                                        "style": {"type": "number"},
                                        "use_agents": {"type": "boolean"},
                                        "prompt_override": {"type": "string"},
                                        "tone": {"type": "string"},
                                        "duration_target_sec": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Audio generated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "text": {"type": "string"},
                                            "voice": {"type": "string"},
                                            "replicate_audio_url": {"type": "string"},
                                            "audio_url": {"type": "string"},
                                            "status": {"type": "string"},
                                            "agent_outputs": {
                                                "$ref": "#/components/schemas/AgentOutputs"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/jobs/{job_id}/start-full": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Run the full UGC ad generation pipeline",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt_override": {"type": "string"},
                                        "product_info": {
                                            "type": "object",
                                            "additionalProperties": True,
                                        },
                                        "actor_variant_id": {"type": "string", "format": "uuid"},
                                        "actor_image_url": {"type": "string"},
                                        "product_image_urls": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "voice": {"type": "string"},
                                        "language_code": {"type": "string"},
                                        "speed": {"type": "number"},
                                        "stability": {"type": "number"},
                                        "similarity_boost": {"type": "number"},
                                        "style": {"type": "number"},
                                        "use_agents": {"type": "boolean"},
                                        "tone": {"type": "string"},
                                        "duration_target_sec": {"type": "integer"},
                                        "hook_text": {"type": "string"},
                                        "story_prompt": {"type": "string"},
                                        "ugc_prompt": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Full pipeline completed",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "status": {"type": "string"},
                                            "actor_variant_id": {"type": "string", "format": "uuid", "nullable": True},
                                            "output_video_url": {"type": "string"},
                                            "manifest_url": {"type": "string"},
                                            "artifacts": {
                                                "type": "object",
                                                "additionalProperties": True,
                                            },
                                            "agent_outputs": {
                                                "$ref": "#/components/schemas/AgentOutputs"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/data": {
                "get": {
                    "tags": ["Utility"],
                    "summary": "Legacy sample data endpoint",
                    "responses": {
                        "200": {"description": "Sample payload"}
                    },
                }
            },
        },
    }
