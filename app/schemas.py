from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    full_name = fields.String(required=True, validate=validate.Length(min=1, max=120))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=1, max=128))


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True, validate=validate.Length(min=32))


class LogoutSchema(RefreshSchema):
    pass


class OAuthSchema(Schema):
    id_token = fields.String(load_default=None)
    access_token = fields.String(load_default=None)
    authorization_code = fields.String(load_default=None)
    redirect_uri = fields.Url(load_default=None)

    @validates_schema
    def validate_token_present(self, data, **_):
        if not any(data.get(key) for key in ("id_token", "access_token", "authorization_code")):
            raise ValidationError("Provide id_token, access_token, or authorization_code.")


class UpdateMeSchema(Schema):
    full_name = fields.String(validate=validate.Length(min=1, max=120))
    avatar_url = fields.Url(allow_none=True)
    gender = fields.String(allow_none=True, validate=validate.OneOf(["male", "female", "other"]))
    age = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=120))
    address = fields.String(allow_none=True, validate=validate.Length(max=255))
    phone_number = fields.String(allow_none=True, validate=validate.Length(max=32))
    bio = fields.String(allow_none=True, validate=validate.Length(max=500))


class TokenPairSchema(Schema):
    access_token = fields.String(required=True)
    refresh_token = fields.String(required=True)
    token_type = fields.String(required=True)


class UserSchema(Schema):
    id = fields.String(required=True)
    email = fields.Email(allow_none=True)
    full_name = fields.String(required=True)
    avatar_url = fields.String(allow_none=True)
    gender = fields.String(allow_none=True)
    age = fields.Integer(allow_none=True)
    address = fields.String(allow_none=True)
    phone_number = fields.String(allow_none=True)
    bio = fields.String(allow_none=True)
    provider = fields.String(required=True)
    role = fields.String(required=True)
    status = fields.String(required=True)
    created_at = fields.String(required=True)
    updated_at = fields.String(required=True)


class ErrorSchema(Schema):
    code = fields.String(required=True)
    message = fields.String(required=True)
    details = fields.Dict(keys=fields.String(), values=fields.Raw(), required=True)


def user_to_dict(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "gender": user.gender,
        "age": user.age,
        "address": user.address,
        "phone_number": user.phone_number,
        "bio": user.bio,
        "provider": user.provider.value,
        "role": user.role.value,
        "status": user.status.value,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
