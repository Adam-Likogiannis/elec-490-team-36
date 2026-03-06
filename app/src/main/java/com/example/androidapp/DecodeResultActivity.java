package com.example.androidapp;

import android.net.Uri;
import android.os.Bundle;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

public class DecodeResultActivity extends ComponentActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_decode_result);

        ImageView img = findViewById(R.id.imgResult);
        TextView tv = findViewById(R.id.tvMessage);

        String uriStr = getIntent().getStringExtra("image_uri");
        String msg = getIntent().getStringExtra("decoded_message");

        if (uriStr != null) img.setImageURI(Uri.parse(uriStr));
        tv.setText("Decoded message:\n\n" + (msg == null ? "(null)" : msg));
    }
}