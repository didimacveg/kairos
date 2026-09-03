# GetSympto+

AI-powered health information tool for symptom analysis, built with a focus on accessibility, privacy, and responsible AI.

## Why I built it

Finding reliable health information online is often harder than it should be. People describe symptoms in natural language, search through multiple websites, and are frequently left with either too much information or no clear indication of what level of attention their situation may require.

I wanted to build a simpler interface: describe what you are experiencing, identify the affected area of the body, and receive structured, understandable information within seconds.

GetSympto+ was designed as an **information and guidance tool, not a diagnostic system**. Its purpose is to help users understand possible causes and decide what level of attention may be appropriate, while clearly avoiding claims of medical diagnosis.

The project also presented an interesting engineering challenge: building an AI-powered application that handles potentially sensitive health-related input while remaining anonymous by default, multilingual, and secure.

## What it does

GetSympto+ allows users to select an affected area through an interactive SVG body map and describe their symptoms using natural language.

The application processes the input with Claude Haiku and returns a structured report containing possible causes, an urgency level, and recommended next steps.

The platform supports **Spanish, English, Chinese, and Russian**. Users can use the core experience anonymously, while authenticated users can save reports, download them as PDFs, and use additional follow-up features.

The application is deployed in production at `getsympto.app`.

## Architecture

The application uses a Next.js-based full-stack architecture deployed on Vercel.

```text
┌─────────────────────────────┐
│          User               │
│  Symptoms + Body Location   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Next.js Frontend      │
│ React + Tailwind + SVG      │
│        next-intl            │
└──────────────┬──────────────┘
               │
               │ POST /api/analyze
               ▼
┌─────────────────────────────┐
│      Next.js API Routes     │
│       Serverless / Vercel   │
├─────────────────────────────┤
│ IP Rate Limiting             │
│ Authentication              │
│ Input Validation             │
│ Security / Sanitization      │
│ Subscription Checks          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Prompt Layer           │
│       lib/prompts.js        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Anthropic API          │
│       Claude Haiku 4.5      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│     Structured JSON Report   │
│ Severity / Causes / Actions  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        Report.jsx            │
│   Results + Follow-up UI     │
└─────────────────────────────┘
```

### Stack

* **Frontend:** Next.js 14 (App Router), React, Tailwind CSS
* **Internationalization:** next-intl
* **Backend:** Next.js API Routes / Vercel Serverless Functions
* **Database:** Supabase / PostgreSQL
* **AI:** Claude Haiku 4.5 via Anthropic API
* **Authentication:** Supabase Auth + Google OAuth
* **Hosting:** Vercel
* **DNS / CDN:** Cloudflare
* **Payments:** Stripe *(integration in progress)*
* **Email:** Resend
* **External APIs:** Open-Meteo
* **Analytics:** Google Analytics 4
* **Languages:** Spanish, English, Chinese, Russian

## Technical decisions

### Next.js for the full stack

I chose Next.js instead of separating the frontend and backend into independent applications.

This allowed the application, API routes, authentication flow, and deployment pipeline to remain within one project while still keeping sensitive operations server-side.

**Trade-off:** the architecture is tightly coupled to the Next.js ecosystem, but the reduced infrastructure complexity was worth it for an MVP.

### Claude Haiku for analysis

I chose Claude Haiku instead of a larger model because the application needed relatively fast structured responses at a lower inference cost.

The model receives a controlled prompt and is expected to return structured JSON containing the relevant analysis fields rather than unrestricted prose.

**Trade-off:** a smaller model can provide less sophisticated reasoning than larger models, so the application is designed around structured information and explicit limitations rather than presenting the output as medical diagnosis.

### Supabase for database and authentication

Supabase provides PostgreSQL, authentication, and the infrastructure required to persist user reports without introducing a separate database and authentication stack.

**Trade-off:** the application becomes partially dependent on Supabase, but this significantly reduced the amount of infrastructure required for the MVP.

### Anonymous-first architecture

The core symptom-analysis experience does not require an account.

Authentication is only needed for persistent features such as saving reports and accessing additional functionality.

**Trade-off:** anonymous usage makes usage limits and abuse prevention more difficult, requiring additional IP-based rate limiting and server-side validation.

## What I implemented

I designed and implemented the core product architecture and functionality, including:

* Full product architecture and technical direction
* Interactive SVG body map
* Symptom input and body-location workflow
* Next.js application structure
* API request flow
* Authentication integration
* Supabase database integration
* Subscription and usage-limit logic
* Input validation and sanitization
* Rate-limiting layer
* AI prompt construction
* Structured AI response handling
* Report rendering
* Multilingual application structure
* Anonymous and authenticated user flows
* PDF report functionality
* Email follow-up architecture
* Production deployment
* Cloudflare domain configuration
* Analytics integration

The project reached a functional MVP and was deployed to production.

## What AI helped with

AI was used as a development tool, not as a replacement for product or architectural decisions.

Claude helped with:

* Implementing parts of the application code
* Refactoring and debugging
* Security hardening
* Generating and reviewing implementation details
* Drafting blog content in four languages

The main product architecture, technical direction, feature decisions, interactive body-map design, and initial project configuration were designed by me.

This distinction matters because the project was built using AI-assisted development, while the responsibility for deciding **what to build, how the system should work, and how its components should interact** remained mine.

## Problems encountered

### Payment providers and health-related categorization

The original payment strategy used third-party payment platforms including Lemon Squeezy and Polar.

Both rejected the application because of its classification as health-adjacent.

This forced a change in the monetization architecture and ultimately led to a migration toward direct Stripe integration.

The integration is currently incomplete, which became the main reason the project is paused.

### Race condition in subscription usage limits

A more interesting engineering problem appeared in the daily analysis-limit logic.

Two requests arriving at approximately the same time could both read the same usage counter before either request had incremented it.

Conceptually:

```text
Request A ──► read usage = 2
Request B ──► read usage = 2

Request A ──► allow request
Request B ──► allow request

Request A ──► increment
Request B ──► increment
```

This meant concurrent requests could potentially bypass the intended daily analysis limit.

The problem was not visible during normal sequential testing because each individual request behaved correctly. It appeared when considering concurrent execution and the atomicity of the read/update operation.

### Responsible handling of health-related AI output

Because the application processes symptom descriptions, the system needed to be designed around the distinction between **information and diagnosis**.

The product therefore avoids presenting its output as a medical diagnosis and instead focuses on possible causes, urgency, and recommended action.

This also influenced the security, payment, and product decisions throughout development.

## How I solved them

For the payment issue, I evaluated alternative providers and identified that the problem was not an implementation error but a **business/category restriction imposed by the payment platforms**.

The architecture was therefore changed toward direct Stripe integration rather than continuing to build around providers that would not support the product category.

For the usage-limit race condition, the issue was traced to the non-atomic relationship between reading and updating the usage counter.

The important lesson was that application-level logic such as:

```text
check → allow → increment
```

is not necessarily safe in a concurrent serverless environment.

The long-term solution is to move the critical operation toward an atomic database-side operation or transaction so that checking and consuming a usage allowance cannot be separated by another request.

For the health-related output, the solution was primarily architectural and product-level: the system was explicitly positioned as an information tool rather than a diagnostic service, with the AI response constrained to the intended structured format.

## What I would change

If I rebuilt GetSympto+ today, I would design the usage-limit system as an atomic database operation from the beginning instead of implementing the check and increment as separate application-level operations.

I would also evaluate payment-provider compatibility **before** building the monetization layer. The payment issue demonstrated that technical feasibility does not guarantee business feasibility.

I would spend more time designing the data model and privacy boundaries before implementing user accounts and persistent reports, especially because health-related inputs require more careful handling than ordinary application data.

Finally, I would establish stronger automated testing around concurrent requests, authentication boundaries, rate limits, and malformed AI responses earlier in development.

## Future roadmap

The project is currently paused after reaching a functional production MVP.

The next priorities are:

1. Complete the Stripe integration.
2. Resolve the usage-limit race condition with an atomic database operation.
3. Complete the symptom follow-up email cron.
4. Expand automated testing for security and concurrent requests.
5. Improve AI response validation and failure handling.
6. Continue refining the authenticated report history and PDF experience.

Some features are intentionally **not** part of the roadmap.

GetSympto+ will not attempt to become a medical diagnostic system. It will not claim to replace doctors or provide definitive diagnoses from symptoms.

The goal is to remain an **accessible information and guidance tool**, using AI where it provides value while keeping the limitations of the technology explicit.

