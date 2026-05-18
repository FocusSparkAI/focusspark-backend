# FocusSpark API - Postman Test Data

## BASE CONFIGURATION

### Variables
```
base_url = http://127.0.0.1:8000
auth_token = (copy from login response)
```

### Headers (for protected routes)
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

---

## 1. AUTHENTICATION ENDPOINTS

### 1.1 Sign Up
**Route:** `POST` `{{base_url}}/auth/signup`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "full_name": "Alex Johnson",
  "email": "alex@example.com",
  "password": "TestPass123!",
  "confirm_password": "TestPass123!",
  "academic_focus": "Computer Science",
  "accepted_terms": true
}
```

**Expected Response (200):**
```json
{
  "id": 1,
  "email": "alex@example.com",
  "full_name": "Alex Johnson"
}
```

---

### 1.2 Login
**Route:** `POST` `{{base_url}}/auth/login`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "alex@example.com",
  "password": "TestPass123!"
}
```

**Expected Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**ACTION:** Copy `access_token` value and save as `{{auth_token}}` variable

---

### 1.3 Get Profile
**Route:** `GET` `{{base_url}}/auth/profile`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
{
  "id": 1,
  "email": "alex@example.com",
  "full_name": "Alex Johnson",
  "academic_focus": "Computer Science",
  "created_at": "2026-05-10T14:30:00"
}
```

---

### 1.4 Delete Account
**Route:** `DELETE` `{{base_url}}/auth/delete-user`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
{
  "message": "User deleted successfully"
}
```

---

## 2. CHAT ENDPOINTS

### 2.1 Get All Chat Threads
**Route:** `GET` `{{base_url}}/chat/threads`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "Operating Systems Help",
    "created_at": "2026-05-10T14:30:00"
  }
]
```

---

### 2.2 Create Chat Thread
**Route:** `POST` `{{base_url}}/chat/threads`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Operating Systems Help"
}
```

**Expected Response (200):**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "Operating Systems Help",
  "created_at": "2026-05-10T14:30:00"
}
```

**ACTION:** Save thread `id` as `{{thread_id}}`

---

### 2.3 Get Chat Messages (by thread_id)
**Route:** `GET` `{{base_url}}/chat/threads/{{thread_id}}`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "thread_id": 1,
    "type": "user",
    "content": "Explain what a process is",
    "created_at": "2026-05-10T14:31:00"
  },
  {
    "id": 2,
    "thread_id": 1,
    "type": "ai",
    "content": "A process is...",
    "created_at": "2026-05-10T14:31:05"
  }
]
```

---

### 2.4 Send Chat Message
**Route:** `POST` `{{base_url}}/chat/`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Explain what a process is in operating systems",
  "thread_id": 1
}
```

**Expected Response (200):**
```json
{
  "response": "A process is a running instance of a program with its own memory space, state, and resources. The operating system manages processes through the process scheduler...",
  "message_id": 42
}
```

**ACTION:** Save message `id` as `{{message_id}}`

---

### 2.5 Alternative Chat Messages (for testing)

**Message 2:**
```json
{
  "message": "What is the difference between multiprogramming and multitasking?",
  "thread_id": 1
}
```

**Message 3:**
```json
{
  "message": "Explain context switching in detail",
  "thread_id": 1
}
```

---

### 2.5 Upload Document & Chat
**Route:** `POST` `{{base_url}}/chat/document`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: multipart/form-data
```

**Request Body (Form Data):**
```
thread_id: 1
message: "Explain this document." (optional, defaults to "Explain this document.")
file: (binary file upload - PDF, TXT, DOCX, etc.)
```

**Expected Response (200):**
```json
{
  "response": "Based on the uploaded document, here's the analysis...",
  "message_id": 43
}
```

**Note:** 
- `file` parameter is required
- `message` parameter is optional (defaults to "Explain this document.")
- Supports common document formats (PDF, TXT, DOCX, images, etc.)

---

### 2.6 Get Message Artifacts
**Route:** `GET` `{{base_url}}/chat/message/{{message_id}}/artifacts`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "message_id": 42,
    "artifact_type": "flashcard_deck",
    "artifact_id": 5
  }
]
```

---

## 3. FLASHCARDS ENDPOINTS

### 3.1 Get All Flashcard Decks
**Route:** `GET` `{{base_url}}/flashcards/`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "Binary Trees Flashcards",
    "topic": "Binary Trees",
    "total_cards": 12,
    "created_at": "2026-05-10T14:30:00"
  }
]
```

**ACTION:** Save deck `id` as `{{deck_id}}`

---

### 3.2 Get Flashcards in a Deck
**Route:** `GET` `{{base_url}}/flashcards/{{deck_id}}`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "deck_id": 1,
    "front": "What is a binary tree?",
    "back": "A tree where each node has at most 2 children (left and right)",
    "position": 1
  },
  {
    "id": 2,
    "deck_id": 1,
    "front": "Define traversal",
    "back": "The process of visiting every node in a tree exactly once",
    "position": 2
  }
]
```

---

### 3.3 Generate Flashcards from Topic
**Route:** `POST` `{{base_url}}/flashcards/generate`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "topic": "Binary Search Trees"
}
```

**Expected Response (200):**
```json
{
  "deck": {
    "id": 5,
    "user_id": 1,
    "title": "Binary Search Trees Flashcards",
    "topic": "Binary Search Trees",
    "total_cards": 10,
    "created_at": "2026-05-10T14:35:00"
  },
  "flashcards": [
    {
      "id": 1,
      "deck_id": 5,
      "front": "Define BST",
      "back": "A binary tree where left subtree < node < right subtree",
      "position": 1
    },
    {
      "id": 2,
      "deck_id": 5,
      "front": "What is inorder traversal?",
      "back": "Left -> Node -> Right traversal pattern",
      "position": 2
    }
  ]
}
```

---

### 3.4 Alternative Topic Ideas
 
---

## Update Log

- Last updated: 2026-05-17 by GitHub Copilot — appended quick update.

```json
{
  "topic": "Dynamic Programming"
}
```

```json
{
  "topic": "Graph Algorithms"
}
```

```json
{
  "topic": "Database Normalization"
}
```

---

### 3.5 Generate Flashcards from Chat
**Route:** `POST` `{{base_url}}/flashcards/from-chat`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "message_id": 42
}
```

**Expected Response:** Same format as 3.3

---

## 4. QUIZ ENDPOINTS

### 4.1 Get All Quizzes
**Route:** `GET` `{{base_url}}/quiz/`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "OS Basics Quiz",
    "topic": "Operating Systems",
    "difficulty": "Beginner",
    "created_at": "2026-05-10T14:30:00"
  }
]
```

**ACTION:** Save quiz `id` as `{{quiz_id}}`

---

### 4.2 Get Quiz Questions
**Route:** `GET` `{{base_url}}/quiz/{{quiz_id}}`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:** (empty)

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "quiz_id": 1,
    "question": "What is a process?",
    "options": ["A file", "A running program", "Memory block", "CPU instruction"],
    "correct_answer_index": 1
  },
  {
    "id": 2,
    "quiz_id": 1,
    "question": "Which scheduler picks the next process?",
    "options": ["Long-term", "Short-term", "Medium-term", "I/O"],
    "correct_answer_index": 1
  }
]
```

---

### 4.3 Generate Quiz - Beginner
**Route:** `POST` `{{base_url}}/quiz/generate`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "topic": "Database Design",
  "difficulty": "Beginner"
}
```

**Expected Response (200):**
```json
{
  "quiz": {
    "id": 3,
    "user_id": 1,
    "title": "Database Design Quiz",
    "topic": "Database Design",
    "difficulty": "Beginner",
    "created_at": "2026-05-10T14:40:00"
  },
  "questions": [
    {
      "id": 1,
      "quiz_id": 3,
      "question": "What is a database?",
      "options": ["A file", "Organized data collection", "Software", "Hardware"],
      "correct_answer_index": 1
    }
  ]
}
```

---

### 4.4 Generate Quiz - Intermediate
**Route:** `POST` `{{base_url}}/quiz/generate`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "topic": "Sorting Algorithms",
  "difficulty": "Intermediate"
}
```

**Expected Response:** Similar to 4.3 format

---

### 4.5 Generate Quiz - Advanced
**Route:** `POST` `{{base_url}}/quiz/generate`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "topic": "Distributed Systems",
  "difficulty": "Advanced"
}
```

**Expected Response:** Similar to 4.3 format

---

### 4.6 Generate Quiz from Chat
**Route:** `POST` `{{base_url}}/quiz/from-chat`

**Headers:**
```
Authorization: Bearer {{auth_token}}
Content-Type: application/json
```

**Request Body:**
```json
{
  "message_id": 42
}
```

**Expected Response:** Similar to 4.3 format

---

## 5. FOCUS & EMOTION DETECTION ENDPOINTS

### 5.1 Single Frame Analysis (POST /analyze)
**Route:** `POST` `{{base_url}}/analyze`

**Headers:**
```
Content-Type: application/json
```

**Note:** This route does NOT require authentication

**Request Body (Option 1 - Minimal Test Image):**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8VAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="
}
```

**Expected Response (200):**
```json
{
  "emotion": "Neutral",
  "focused": true,
  "metrics": {
    "reason": "ok"
  }
}
```

**Possible Emotion Values:** Angry, Disgust, Fear, Happy, Neutral, Sad, Surprise

---

### 5.2 How to Use Your Own Image

1. Take a screenshot or find any .jpg image
2. Go to: https://www.base64encode.org/
3. Upload your image
4. Copy the base64 string
5. Replace the base64 in the request with your string (keep `data:image/jpeg;base64,` prefix)

---

### 5.3 Real-time WebSocket (WS /ws)
**Route:** `WebSocket` `ws://127.0.0.1:8000/ws`

**Connection:** Direct WebSocket connection (no auth required)

**Send Frame (text):**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8VAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="
}
```

**Receive Response (continuous):**
```json
{
  "emotion": "Happy",
  "focused": true,
  "metrics": {
    "reason": "ok"
  }
}
```

**Error Responses:**
```json
{
  "error": "image_required"
}
```

```json
{
  "error": "invalid_json"
}
```

---

## 6. TEST FLOW (RECOMMENDED ORDER)

1. ✅ **POST** `{{base_url}}/auth/signup`
2. ✅ **POST** `{{base_url}}/auth/login` → Save token
3. ✅ **GET** `{{base_url}}/auth/profile` → Verify user
4. ✅ **POST** `{{base_url}}/chat/threads` → Create thread
5. ✅ **POST** `{{base_url}}/chat/` → Send message
6. ✅ **GET** `{{base_url}}/chat/threads` → List threads
7. ✅ **POST** `{{base_url}}/flashcards/generate` → Generate flashcards
8. ✅ **GET** `{{base_url}}/flashcards/` → List decks
9. ✅ **GET** `{{base_url}}/flashcards/{{deck_id}}` → View cards
10. ✅ **POST** `{{base_url}}/quiz/generate` → Generate quiz
11. ✅ **GET** `{{base_url}}/quiz/` → List quizzes
12. ✅ **POST** `{{base_url}}/analyze` → Test focus detection

---

## 7. COMMON STATUS CODES

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Quiz generated successfully |
| 201 | Created | New resource created |
| 400 | Bad Request | Invalid email format |
| 401 | Unauthorized | Missing/expired token |
| 403 | Forbidden | No permission for resource |
| 404 | Not Found | Thread ID doesn't exist |
| 500 | Server Error | Database connection failed |
| 502 | AI Provider Error | OpenAI API unreachable |

---

## 8. TROUBLESHOOTING

### 500 Error on Auth Endpoints
Check:
1. Database URL is correct in `.env`
2. MySQL server is running
3. `GITHUB_TOKEN` is set (for AI features)
4. JWT_SECRET is set in `.env`

### 502 Error on Quiz/Flashcard Generation
Check:
1. `GITHUB_TOKEN` is valid
2. GitHub Models API is accessible
3. API rate limit not exceeded

### Empty Responses
Check:
1. Authorization header is present
2. Token is not expired
3. User exists in database

