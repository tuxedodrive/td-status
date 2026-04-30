# TuxedoDrive Status

[![Conforms to README.lint](https://img.shields.io/badge/README.lint-conforming-brightgreen)](https://github.com/discoveryworks/readme-dot-lint)

**Live status page:** [status.tuxedodrive.dev](https://status.tuxedodrive.dev)

# 🌌 Why did we create this status page?

TuxedoDrive depends on first-party services and external providers. When something goes wrong, we need to know immediately—and so do our users. This status page provides transparency and automated monitoring so we can respond to outages quickly.

# 🌌🌌 Who benefits from it?

- **TuxedoDrive users** who want to check if an issue is on our end
- **The TuxedoDrive team** who need immediate alerts when services fail

# 🌌🌌🌌 What does it do?

Monitors 10 critical checks across our platform:

- **First-party health checks** - Production application and Edge API health endpoints
- **Payment Provider Reachability** - Stripe unauthenticated provider reachability
- **Email Provider Reachability** - Postmark unauthenticated provider reachability
- **SMS Provider Reachability** - Twilio unauthenticated provider reachability
- **Authentication** - Google OAuth
- **Environmental Data Provider Reachability** - OpenWeather and Google Pollen unauthenticated provider reachability
- **Infrastructure Provider Reachability** - Render and Doppler

External provider checks are reachability checks unless otherwise stated. A green provider reachability check means the provider endpoint responded with an expected non-5xx or documented unauthenticated status. It does not prove that TuxedoDrive credentials, account permissions, or end-to-end business workflows are healthy.

Authenticated synthetic checks for payment, email, SMS, weather, pollen, and secrets workflows are planned separately from this Upptime reachability layer.

# 🌌🌌🌌🌌 How does it work?

Powered by [Upptime](https://upptime.js.org), this runs automated checks every 15 minutes via GitHub Actions. With the current threshold of 5 failed checks, the expected time to mark a check down is up to about 75 minutes. When a service goes down:

1. A GitHub issue is created
2. The team is notified via email
3. The status page updates automatically

# 🌌🌌🌌🌌🌌 Extras

## License

- Code: [MIT](./LICENSE)
- Data in `./history`: [Open Database License](https://opendatacommons.org/licenses/odbl/1-0/)
