from flask import jsonify, _request_ctx_stack, current_app as app
from functools import wraps
from six.moves.urllib.request import urlopen
from jose import jwt
import json

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class Auth():
    def __init__(self):
        self.AUTH0_DOMAIN = 'dev-0fw6q03t.auth0.com'
        self.API_AUDIENCE = 'localhost'
        self.ALGORITHMS = ["RS256"]
    
    def get_jwks(self):
        return json.loads(urlopen("https://" + self.AUTH0_DOMAIN + "/.well-known/jwks.json").read())

    @app.errorhandler(AuthError)
    def handle_auth_error(self, ex):
        response = jsonify(ex.error)
        response.status_code = ex.status_code
        return response

    def get_token_auth_header(self, request):
        """Obtains the access token from the Authorization Header
        """
        auth = request.headers.get("Authorization", None)
        if not auth:
            raise AuthError({"code": "authorization_header_missing",
                            "description":
                            "Authorization header is expected"}, 401)

        parts = auth.split()

        if parts[0].lower() != "bearer":
            raise AuthError({"code": "invalid_header",
                            "description":
                            "Authorization header must start with"
                            " Bearer"}, 401)
        elif len(parts) == 1:
            raise AuthError({"code": "invalid_header",
                            "description": "Token not found"}, 401)
        elif len(parts) > 2:
            raise AuthError({"code": "invalid_header",
                            "description":
                            "Authorization header must be"
                            " Bearer token"}, 401)

        token = parts[1]
        return token

    def auth_required(self, request):
        def requires_auth(f):
            """Determines if the access token is valid
            """
            @wraps(f)
            def decorated(*args, **kwargs):
                token = self.get_token_auth_header(request)
                jsonurl = urlopen("https://"+self.AUTH0_DOMAIN+"/.well-known/jwks.json")
                jwks = json.loads(jsonurl.read())
                unverified_header = jwt.get_unverified_header(token)
                rsa_key = {}
                for key in jwks["keys"]:
                    if key["kid"] == unverified_header["kid"]:
                        rsa_key = {
                            "kty": key["kty"],
                            "kid": key["kid"],
                            "use": key["use"],
                            "n": key["n"],
                            "e": key["e"]
                        }
                if rsa_key:
                    try:
                        payload = jwt.decode(
                            token,
                            rsa_key,
                            algorithms=self.ALGORITHMS,
                            audience=self.API_AUDIENCE,
                            issuer="https://"+self.AUTH0_DOMAIN+"/"
                        )
                    except jwt.ExpiredSignatureError:
                        raise AuthError({"code": "token_expired",
                                        "description": "token is expired"}, 401)
                    except jwt.JWTClaimsError:
                        raise AuthError({"code": "invalid_claims",
                                        "description":
                                        "incorrect claims,"
                                        "please check the audience and issuer"}, 401)
                    except Exception:
                        raise AuthError({"code": "invalid_header",
                                        "description":
                                        "Unable to parse authentication"
                                        " token."}, 400)

                    _request_ctx_stack.top.current_user = payload
                    return f(*args, **kwargs)
                raise AuthError({"code": "invalid_header",
                                "description": "Unable to find appropriate key"}, 400)
            return decorated
        return requires_auth