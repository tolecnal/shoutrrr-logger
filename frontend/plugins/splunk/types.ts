export interface SplunkFieldMapping {
  output_key: string;
  /** One of:
   *  - A top-level notification field: id, message, title, sender_name, received_at, source_ip
   *  - A custom field: custom_fields.<key>
   *  - A literal value: literal:<value>
   */
  source_field: string;
}

export interface SplunkConfig {
  hec_url: string;
  hec_token: string;
  index: string;
  source: string;
  sourcetype: string;
  field_mappings: SplunkFieldMapping[];
  verify_tls: boolean;
}
