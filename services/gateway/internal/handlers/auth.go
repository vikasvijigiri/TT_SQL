package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/nquire/ttsql/gateway/internal/config"
)

type googleAuthRequest struct {
	AccessToken string `json:"access_token" binding:"required"`
}

type googleTokenInfo struct {
	Azp           string `json:"azp"`
	Aud           string `json:"aud"`
	Sub           string `json:"sub"`
	Scope         string `json:"scope"`
	Exp           string `json:"exp"`
	ExpiresIn     string `json:"expires_in"`
	Email         string `json:"email"`
	EmailVerified string `json:"email_verified"`
	AccessType    string `json:"access_type"`
	Error         string `json:"error"`
	ErrorDesc     string `json:"error_description"`
}

type googleUserInfo struct {
	Sub     string `json:"sub"`
	Name    string `json:"name"`
	Picture string `json:"picture"`
	Email   string `json:"email"`
}

type authClaims struct {
	Email   string `json:"email"`
	Name    string `json:"name"`
	Picture string `json:"picture"`
	Sub     string `json:"sub"`
	jwt.RegisteredClaims
}

// GoogleAuthHandler verifies a Google access token, then issues a signed JWT.
//
//	POST /api/auth/google
//	Body: { "access_token": "<google access token>" }
func GoogleAuthHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req googleAuthRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "access_token is required"})
			return
		}

		// 1. Verify token with Google's tokeninfo endpoint.
		tokenInfo, err := fetchGoogleTokenInfo(req.AccessToken)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "failed to verify Google token"})
			return
		}
		if tokenInfo.Error != "" {
			c.JSON(http.StatusUnauthorized, gin.H{"error": tokenInfo.ErrorDesc})
			return
		}

		// 2. If a Client ID is configured, enforce audience check.
		if cfg.GoogleClientID != "" && tokenInfo.Aud != cfg.GoogleClientID && tokenInfo.Azp != cfg.GoogleClientID {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "token audience mismatch"})
			return
		}

		// 3. Fetch user profile from Google.
		profile, err := fetchGoogleUserInfo(req.AccessToken)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch user profile"})
			return
		}

		// 4. Issue a signed JWT valid for 24 hours.
		claims := authClaims{
			Email:   profile.Email,
			Name:    profile.Name,
			Picture: profile.Picture,
			Sub:     profile.Sub,
			RegisteredClaims: jwt.RegisteredClaims{
				Issuer:    "nquire.ai",
				Subject:   profile.Sub,
				IssuedAt:  jwt.NewNumericDate(time.Now()),
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
			},
		}

		token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
		signed, err := token.SignedString([]byte(cfg.JWTSecret))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to sign token"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"token": signed,
			"user": gin.H{
				"email":   profile.Email,
				"name":    profile.Name,
				"picture": profile.Picture,
				"sub":     profile.Sub,
			},
		})
	}
}

func fetchGoogleTokenInfo(accessToken string) (*googleTokenInfo, error) {
	url := fmt.Sprintf("https://www.googleapis.com/oauth2/v3/tokeninfo?access_token=%s", accessToken)
	resp, err := http.Get(url) //nolint:noctx
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var info googleTokenInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, err
	}
	return &info, nil
}

func fetchGoogleUserInfo(accessToken string) (*googleUserInfo, error) {
	req, err := http.NewRequest("GET", "https://www.googleapis.com/oauth2/v3/userinfo", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var info googleUserInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, err
	}
	return &info, nil
}
